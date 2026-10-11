"""Story adapter against the actual firmware core through a serial pseudo-terminal."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tty
from uuid import uuid4

import pytest

from magneto_harness.devices.story_cell import AcknowledgedCell


@pytest.fixture(scope='module')
def firmware(tmp_path_factory):
    compiler = shutil.which('c++')
    if not compiler or sys.platform == 'win32':
        pytest.skip('requires C++ and POSIX pseudo-terminals')
    root = Path(__file__).resolve().parents[2] / 'cell-firmware'
    binary = tmp_path_factory.mktemp('story-firmware') / 'cell_sim'
    subprocess.run([compiler, '-std=c++11', '-O1', '-o', str(binary),
                    str(root / 'sim/cell_sim.cpp'), str(root / 'magneto_cell/cell_core.cpp')], check=True)
    return binary


@pytest.mark.parametrize('boot_ms', [1500, 0])
def test_story_commands_with_reset_and_already_booted_controller(firmware, boot_ms):
    master, slave = os.openpty()
    tty.setraw(slave)
    process = subprocess.Popen([str(firmware), '-d', str(boot_ms)], stdin=master, stdout=master)
    cell = None
    try:
        if boot_ms == 0:
            time.sleep(.15)  # READY is discarded by serial open, as on a running board.
        cell = AcknowledgedCell(os.ttyname(slave))
        for operation, target, command, mask in [('show','r','DOTS 1235','17'),
                                                ('show','rabbit','SPELL rabbit','17'),
                                                ('clear','','CLEAR','00')]:
            identity = str(uuid4())
            result = cell.execute({'command_id':identity,'operation':operation,'target':target})
            assert result['command_id'] == identity
            assert result['cell_ack'] is True
            assert result['command'] == command
            assert result['receipt'].split()[1] == mask
            assert result['sequence_started'] == (len(target) > 1)
            assert result['sequence_complete'] is False
    finally:
        if cell:
            cell.close()
        process.terminate()
        process.wait(timeout=2)
        os.close(master)
        os.close(slave)


def test_preflight_never_opens_or_actuates_serial(tmp_path, monkeypatch, capsys):
    import json
    from magneto_harness.devices import story_cell
    from magneto_harness import config
    port = tmp_path / 'serial-port'
    port.touch()
    monkeypatch.setattr(sys, 'argv', ['story_cell', '--check'])
    monkeypatch.setattr(config, 'load_config', lambda: {'cell': {'port': str(port), 'baud': 115200}})
    def forbidden(*args, **kwargs):
        pytest.fail('read-only check opened physical serial')
    monkeypatch.setattr(story_cell, 'AcknowledgedCell', forbidden)
    story_cell.main()
    result = json.loads(capsys.readouterr().out)
    assert result['port_accessible'] is True
    assert result['physical_ready'] is False
    port.unlink()
    with pytest.raises(SystemExit) as error:
        story_cell.main()
    assert error.value.code == 1

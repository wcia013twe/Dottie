"""SSH transport alone must not turn the Nano status green."""
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'orin-harness'))
from magneto_harness.devices.nano_status import probe

class NanoStatusTests(unittest.TestCase):
    def test_no_target_never_connects(self):
        run=Mock()
        self.assertEqual(probe(None,run)['state'],'not_configured')
        run.assert_not_called()

    def test_invalid_target_never_runs_ssh(self):
        for target in ['-oProxyCommand=bad','host;echo bad','user@host cat','$(bad)','host\nother']:
            run=Mock()
            self.assertEqual(probe(target,run)['state'],'invalid')
            run.assert_not_called()

    def test_failed_ssh_is_unverified(self):
        run=Mock(return_value=subprocess.CompletedProcess([],255,'','failure'))
        self.assertEqual(probe('wes@nano.local',run)['state'],'unverified')

    def test_other_device_is_not_connected(self):
        run=Mock(return_value=subprocess.CompletedProcess([],0,'Raspberry Pi 5\x00',''))
        self.assertEqual(probe('nano.local',run)['state'],'wrong_device')

    def test_verified_nano_does_not_claim_runtime(self):
        run=Mock(return_value=subprocess.CompletedProcess([],0,'NVIDIA Jetson Orin Nano Developer Kit\x00',''))
        result=probe('wes@nano.local',run)
        self.assertEqual(result['state'],'connected')
        self.assertIn('runtime connection is not verified',result['message'])
        command=run.call_args.args[0]
        self.assertIn('StrictHostKeyChecking=yes',command)
        self.assertIn('BatchMode=yes',command)
        self.assertEqual(command[-1],'cat /proc/device-tree/model')

    def test_timeout_is_unverified(self):
        run=Mock(side_effect=subprocess.TimeoutExpired('ssh',5))
        self.assertEqual(probe('nano.local',run)['state'],'unverified')

"""Read-only Nano identity probe. Never actuates hardware or starts the harness."""
import re
import subprocess

TARGET = re.compile(r'(?:[a-zA-Z0-9_][a-zA-Z0-9_.-]*@)?[a-zA-Z0-9][a-zA-Z0-9_.-]{0,252}')


def probe(target, run=subprocess.run):
    if not target:
        return {'state': 'not_configured', 'message': 'Nano address not configured.'}
    if not isinstance(target, str) or not TARGET.fullmatch(target):
        return {'state': 'invalid', 'message': 'Nano address is invalid.'}
    try:
        result = run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                      '-o', 'ConnectTimeout=3', '-o', 'ConnectionAttempts=1', '-o', 'ClearAllForwardings=yes',
                      '-o', 'ControlMaster=no', '-o', 'ControlPath=none', target,
                      "cat /proc/device-tree/model"], capture_output=True, text=True, timeout=5)
        if result.returncode:
            return {'state': 'unverified', 'message': 'Could not verify Nano. Check its address, network and trusted SSH access.'}
        model = result.stdout.strip().strip('\x00')
        if not re.search(r'\bJetson (?:Orin )?Nano\b', model, re.IGNORECASE):
            return {'state': 'wrong_device', 'message': 'The host responded, but its device model is not a Jetson Nano.'}
        return {'state': 'connected', 'message': 'Jetson Nano identity verified over SSH. App runtime connection is not verified.'}
    except (OSError, subprocess.TimeoutExpired):
        return {'state': 'unverified', 'message': 'Nano connection could not be verified.'}

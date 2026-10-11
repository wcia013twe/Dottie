import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'orin-harness'))
from story_mode.controller import Controller,StoryError
from magneto_harness.devices.story_cell import AcknowledgedCell,validate

class DeviceActivityTests(TestCase):
    def setUp(self):
        self.controller=Controller();self.state=self.controller.create()
        self.state=self.controller.call(self.state['session_id'],0,'set_context',{'passage_id':'rabbit'},actor='teacher')
        self.state=self.controller.call(self.state['session_id'],self.state['revision'],'propose_activity',{'activity':'identify','target':'r','prompt':'What letter do you feel?','hint':'Feel each dot.','reason':'Story letter.'})
    def test_ack_is_required_and_duplicate_revision_never_resends(self):
        send=Mock(return_value={'connected':True,'cell_ack':True,'state':'acknowledged','ready':True})
        result=self.controller.start_device_activity(self.state['session_id'],self.state['revision'],send)
        self.assertEqual(result['phase'],'waiting_response')
        self.assertTrue(result['braille']['physical_ready'])
        send.assert_called_once_with('show','r')
        with self.assertRaises(StoryError):self.controller.start_device_activity(self.state['session_id'],self.state['revision'],send)
        self.assertEqual(send.call_count,1)
        self.assertEqual(result['observations'],[])
    def test_failed_device_is_not_a_learner_outcome(self):
        result=self.controller.start_device_activity(self.state['session_id'],self.state['revision'],lambda *a:{'connected':False,'cell_ack':False})
        self.assertEqual(result['phase'],'proposed');self.assertEqual(result['observations'],[])
        self.assertNotIn('braille',result)
    def test_release_invalidates_pending_start(self):
        self.controller.release_device(self.state['session_id'],lambda *a:{'cell_ack':True})
        send=Mock()
        with self.assertRaises(StoryError):self.controller.start_device_activity(self.state['session_id'],self.state['revision'],send)
        send.assert_not_called()

class SerialReceiptTests(TestCase):
    def test_command_needs_new_matching_cell_receipt(self):
        cell=AcknowledgedCell.__new__(AcknowledgedCell)
        cell.serial=Mock();cell.write=Mock();cell.expect=Mock(side_effect=['OK','CELL 17 -'])
        request={'command_id':'00000000-0000-4000-8000-000000000001','operation':'show','target':'r'}
        result=cell.execute(request)
        cell.write.assert_called_once_with('DOTS 1235')
        matches=cell.expect.call_args_list[1].args[0]
        self.assertFalse(matches('CELL 01 a'));self.assertTrue(matches('CELL 17 -'))
        self.assertTrue(result['cell_ack'])
    def test_timeout_does_not_report_ack(self):
        cell=AcknowledgedCell.__new__(AcknowledgedCell);cell.serial=Mock();cell.write=Mock();cell.expect=Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):cell.execute({'command_id':'00000000-0000-4000-8000-000000000001','operation':'clear','target':''})
    def test_target_cannot_be_raw_serial_command(self):
        for target in ['r\nCLEAR','rabbit;bad','a'*17,'R']:
            with self.assertRaises(ValueError):validate({'command_id':'00000000-0000-4000-8000-000000000001','operation':'show','target':target})

if __name__=='__main__':main()

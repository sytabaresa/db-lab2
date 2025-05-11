import pytest
from lock_manager import LockManager


class TestSimpleStr:
    """Test of the simple module with the example given in the exercise"""

    @pytest.fixture
    def lock_manager(self):
        return LockManager()

    def test_invalid_format(self, lock_manager):
      # Test invalid format
        with pytest.raises(ValueError):
            lock_manager.process_request_str("Invalid")

        with pytest.raises(ValueError):
            lock_manager.process_request_str("Xlock A A")
            
        with pytest.raises(ValueError):
            lock_manager.process_request_str("Xlock 100 100")
            
        with pytest.raises(ValueError):
            lock_manager.process_request_str("Xlock 100 A A")
                        
    def test_complex_scenario(self, lock_manager):
        program = [
            ('Start 100', 'Start 100 : Transaction 100 started'),
            ('Start 200', 'Start 200 : Transaction 200 started'),
            ('SLock 100 A', 'SLock 100 A: Lock granted'),
            ('XLock 200 A', 'XLock 200 A: Waiting for lock (S-lock held by: 100)'),
            ('Unlock 100 A', [
                'Unlock 100 A: Lock released',
                'X-Lock granted to 200'
            ]),
            ('XLock 100 B', 'XLock 100 B: Lock granted'),
            ('XLock 200 B', 'XLock 200 B: Waiting for lock (X-lock held by: 100)'),
            ('XLock 100 A', 'XLock 100 A: Waiting for lock (X-lock held by: 200)'),
            ('End 100', [
                'End 100 : Transaction 100 ended',
                'Release X-lock on B',
                'X-Lock on B granted to 200'
            ]),
            ('Unlock 200 A', 'Unlock 200 A: Lock released'),
            ('End 200', 'End 200 : Transaction 200 ended')
        ]

        requests = [t[0] for t in program]
        outputs = ['\n'.join(t[1]) if type(t[1]) == list else t[1]
                   for t in program]

        program = ["\n".join(lock_manager.process_request_str(request))
                   for request in requests]
        assert program == outputs

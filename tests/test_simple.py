import pytest
from lock_manager import LockManager, States


class TestSimple:
    """Test of the simple module"""

    @pytest.fixture(scope="function")  # Explicit function scope
    def lock_manager(self):
        return LockManager()

    def test_isolation_verification(self, lock_manager):
        lock_manager.process_request_str("Start 100")
        assert 100 in lock_manager.transactions

    def test_isolation_check(self, lock_manager):
        # This should fail if state isn't reset
        assert 100 not in lock_manager.transactions

    def test_start_transaction(self, lock_manager):
        # Test starting a new transaction
        assert "Transaction 100 started" in lock_manager.process_request_str(
            "Start 100")
        assert 100 in lock_manager.transactions

        # Test starting an existing transaction
        with pytest.raises(ValueError, match='Transaction 100 already started'):
            lock_manager.process_request_str("Start 100")

    def test_end_transaction(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("SLock 100 A")

        # Test ending a transaction
        output = lock_manager.process_request_str("End 100")
        assert "End 100 : Transaction 100 ended" in output
        assert "Release S-lock on A" in output
        assert 100 not in lock_manager.transactions
        assert "A" not in lock_manager.held_locks.get(100, {})

        # Test ending non-existent transaction
        with pytest.raises(ValueError, match='Transaction 200 not started'):
            lock_manager.process_request_str("End 200")

    def test_slock_acquisition(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")

        # Test acquiring S lock
        assert "SLock 100 A: Lock granted" in lock_manager.process_request_str(
            "SLock 100 A")
        assert ("A", States.slock) in [(k, v)
                                       for k, v in lock_manager.held_locks[100].items()]

        # Test acquiring S lock when already held
        assert "SLock 100 A: Lock already held" in lock_manager.process_request_str(
            "SLock 100 A")

    def test_xlock_acquisition(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")

        # Test acquiring X lock
        assert "XLock 100 A: Lock granted" in lock_manager.process_request_str(
            "XLock 100 A")
        assert ("A", States.xlock) in [(k, v)
                                       for k, v in lock_manager.held_locks[100].items()]

        # Test acquiring X lock when already held
        assert "XLock 100 A: Lock already held" in lock_manager.process_request_str(
            "XLock 100 A")

    def test_slock_no_conflicts(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("Start 200")

        # Test S lock no conflict with S lock request
        lock_manager.process_request_str("SLock 100 A")
        output = lock_manager.process_request_str("SLock 200 A")
        assert "SLock 200 A: Lock granted" in output

    def test_lock_conflicts(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("Start 200")

        # Test S lock conflict with X lock request
        lock_manager.process_request_str("SLock 100 A")
        output = lock_manager.process_request_str("XLock 200 A")
        assert "XLock 200 A: Waiting for lock" in output
        assert "S-lock held by: 100" in output

        # Test X lock conflict with S lock request
        lock_manager.process_request_str("XLock 100 B")
        output = lock_manager.process_request_str("SLock 200 B")
        assert "SLock 200 B: Waiting for lock" in output
        assert "X-lock held by: 100" in output

        # Test X lock conflict with X lock request
        lock_manager.process_request_str("XLock 100 C")
        output = lock_manager.process_request_str("XLock 200 C")
        assert "XLock 200 C: Waiting for lock" in output
        assert "X-lock held by: 100" in output

    @pytest.mark.skip(reason="Temporarily disabled")
    def test_lock_upgrade(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("SLock 100 A")

        # Test successful upgrade
        assert "Lock upgraded" in lock_manager.process_request_str(
            "XLock 100 A")
        assert ("A", "X") in [(k, v)
                              for k, v in lock_manager.held_locks[100].items()]

        # Setup for blocked upgrade
        lock_manager.process_request_str("Start 200")
        lock_manager.process_request_str("SLock 100 B")
        lock_manager.process_request_str("SLock 200 B")

        # Test blocked upgrade
        output = lock_manager.process_request_str("XLock 100 B")
        assert "Waiting for lock upgrade" in output
        assert "S-lock held by: 200" in output

    def test_unlock(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("SLock 100 A")
        lock_manager.process_request_str("Start 200")
        lock_manager.process_request_str("XLock 200 A")  # This will wait

        # Test unlock
        output = lock_manager.process_request_str("Unlock 100 A")
        assert "Unlock 100 A: Lock released" in output
        assert "X-Lock granted to 200" in output
        assert ("A", States.xlock) in [(k, v)
                                       for k, v in lock_manager.held_locks[200].items()]

    def test_unlock_end_transaction(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("Start 200")
        lock_manager.process_request_str("SLock 100 A")
        lock_manager.process_request_str("XLock 200 A")  # This will wait

        # Test unlock
        output = lock_manager.process_request_str("End 100")
        assert "End 100 : Transaction 100 ended" in output
        assert "Release S-lock on A" in output
        assert "X-Lock on A granted to 200" in output
        assert ("A", States.xlock) in [(k, v)
                                       for k, v in lock_manager.held_locks[200].items()]
        assert 100 not in lock_manager.transactions
        assert "A" not in lock_manager.held_locks.get(100, {})

    def test_end_waiting_transaction(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("Start 200")
        lock_manager.process_request_str("XLock 100 A")
        lock_manager.process_request_str("XLock 200 A")  # This will wait
        
        # Test unlock
        output = lock_manager.process_request_str("End 200")
        assert "End 200 : Transaction 200 ended" in output
        assert "Release" not in output
        assert "granted" not in output
        assert ("A", States.xlock) in [(k, v)
                                       for k, v in lock_manager.held_locks[100].items()]
        assert 200 not in lock_manager.transactions
        assert "A" not in lock_manager.held_locks.get(200, {})
        assert 200 not in lock_manager.resource_fifo.get("A", {})
        assert "A" in lock_manager.held_locks.get(100, {})

    def test_fifo_waiting_policy(self, lock_manager):
        # Setup
        lock_manager.process_request_str("Start 100")
        lock_manager.process_request_str("Start 200")
        lock_manager.process_request_str("Start 300")
        lock_manager.process_request_str("XLock 100 A")

        # Request locks that will wait
        lock_manager.process_request_str("SLock 200 A")
        lock_manager.process_request_str("SLock 300 A")

        # Release lock - should go to 200 first (FIFO)
        output = lock_manager.process_request_str("Unlock 100 A")
        assert "S-Lock granted to 200" in output
        assert "S-Lock granted to 300" not in output  # Only one should be granted

        # Release again - should go to 300
        output = lock_manager.process_request_str("Unlock 200 A")
        assert "S-Lock granted to 300" in output

    def test_complex_scenario(self, lock_manager):
        # Test the exact scenario from the problem statement
        outputs = []
        outputs.append(lock_manager.process_request_str("Start 100")) # 0
        outputs.append(lock_manager.process_request_str("Start 200")) # 1
        outputs.append(lock_manager.process_request_str("SLock 100 A")) # 2
        outputs.append(lock_manager.process_request_str("XLock 200 A")) # 3
        outputs.append(lock_manager.process_request_str("Unlock 100 A")) # 4
        outputs.append(lock_manager.process_request_str("XLock 100 B")) # 5
        outputs.append(lock_manager.process_request_str("XLock 200 B")) # 6
        outputs.append(lock_manager.process_request_str("XLock 100 A")) # 7
        outputs.append(lock_manager.process_request_str("End 100")) # 8
        outputs.append(lock_manager.process_request_str("Unlock 200 A")) # 9
        outputs.append(lock_manager.process_request_str("End 200")) # 10

        # Verify key outputs
        assert "Transaction 100 started" in outputs[0]
        assert "Lock granted" in outputs[2]
        assert "Waiting for lock" in outputs[3]
        assert "X-Lock granted to 200" in outputs[4]
        assert "X-Lock on B granted to 200" in outputs[8]
        assert "Transaction 200 ended" in outputs[10]

    def test_invalid_requests(self, lock_manager):
        # Test lock requests for non-existent transactions
        with pytest.raises(ValueError, match="Transaction not found"):
            lock_manager.process_request_str("SLock 100 A")
            lock_manager.process_request_str("XLock 100 A")
            lock_manager.process_request_str("Unlock 100 A")

        # Test invalid request types
        with pytest.raises(IndexError):
            lock_manager.process_request_str("Invalid 100")

        # Test invalid request types
        with pytest.raises(IndexError):
            lock_manager.process_request_str("Invalid 100 A")

    def test_invalid_format(self, lock_manager):
      # Test invalid format
        with pytest.raises(IndexError):
            lock_manager.process_request_str("Invalid")

        with pytest.raises(IndexError):
            lock_manager.process_request_str("Xlock A A")
            
        with pytest.raises(IndexError):
            lock_manager.process_request_str("Xlock 100 100")
            
        with pytest.raises(IndexError):
            lock_manager.process_request_str("Xlock 100 A A")
                        
    def test_example_scenario(self, lock_manager):
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
            ('End 200', [
                'End 200 : Transaction 200 ended',
                'Release X-lock on B'
            ])
        ]

        requests = [t[0] for t in program]
        test_outputs = ['\n'.join(t[1]) if type(t[1]) == list else t[1]
                   for t in program]

        for i in range(len(program)):
            assert test_outputs[i] == lock_manager.process_request_str(requests[i])
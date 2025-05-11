import pytest
from lock_manager import LockManager


class TestSimple:
    """Test of the simple module"""

    @pytest.fixture
    def lock_manager(self):
        return LockManager()

    def test_start_transaction(self, lock_manager):
        # Test starting a new transaction
        assert "Transaction 100 started" in lock_manager.process_request(
            "Start", 100)
        assert 100 in lock_manager.transactions

        # Test starting an existing transaction
        assert "already exists" in lock_manager.process_request("Start", 100)

    def test_end_transaction(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)
        lock_manager.process_request("SLock", 100, "A")

        # Test ending a transaction
        output = lock_manager.process_request("End", 100)
        assert "End 100: Transaction 100 ended" in output
        assert "Release S-lock on A" in output
        assert 100 not in lock_manager.transactions
        assert "A" not in lock_manager.held_locks.get(100, {})

        # Test ending non-existent transaction
        assert "not found" in lock_manager.process_request("End", 200)

    def test_slock_acquisition(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)

        # Test acquiring S lock
        assert "SLock 100 A: Lock granted" in lock_manager.process_request(
            "SLock", 100, "A")
        assert ("A", "S") in [(k, v)
                              for k, v in lock_manager.held_locks[100].items()]

        # Test acquiring S lock when already held
        assert "SLock 100 A: Lock already held" in lock_manager.process_request(
            "SLock", 100, "A")

    def test_xlock_acquisition(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)

        # Test acquiring X lock
        assert "XLock 100 A: Lock granted" in lock_manager.process_request(
            "XLock", 100, "A")
        assert ("A", "X") in [(k, v)
                              for k, v in lock_manager.held_locks[100].items()]

        # Test acquiring X lock when already held
        assert "XLock 100 A: Lock already held" in lock_manager.process_request(
            "XLock", 100, "A")

    def test_slock_no_conflicts(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)
        lock_manager.process_request("Start", 200)

        # Test S lock no conflict with S lock request
        lock_manager.process_request("SLock", 100, "A")
        output = lock_manager.process_request("SLock", 200, "A")
        assert "SLock 200 A: Lock granted" in output


    def test_lock_conflicts(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)
        lock_manager.process_request("Start", 200)

        # Test S lock conflict with X lock request
        lock_manager.process_request("SLock", 100, "A")
        output = lock_manager.process_request("XLock", 200, "A")
        assert "XLock 200 A: Waiting for lock" in output
        assert "S-lock held by: 100" in output

        # Test X lock conflict with S lock request
        lock_manager.process_request("XLock", 100, "B")
        output = lock_manager.process_request("SLock", 200, "B")
        assert "SLock 200 B: Waiting for lock" in output
        assert "X-lock held by: 100" in output

        # Test X lock conflict with X lock request
        lock_manager.process_request("XLock", 100, "C")
        output = lock_manager.process_request("XLock", 200, "C")
        assert "XLock 200 B: Waiting for lock" in output
        assert "X-lock held by: 100" in output

    def test_lock_upgrade(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)
        lock_manager.process_request("SLock", 100, "A")

        # Test successful upgrade
        assert "Lock upgraded" in lock_manager.process_request(
            "XLock", 100, "A")
        assert ("A", "X") in [(k, v)
                              for k, v in lock_manager.held_locks[100].items()]

        # Setup for blocked upgrade
        lock_manager.process_request("Start", 200)
        lock_manager.process_request("SLock", 100, "B")
        lock_manager.process_request("SLock", 200, "B")

        # Test blocked upgrade
        output = lock_manager.process_request("XLock", 100, "B")
        assert "Waiting for lock upgrade" in output
        assert "S-lock held by: 200" in output

    def test_unlock(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)
        lock_manager.process_request("SLock", 100, "A")
        lock_manager.process_request("Start", 200)
        lock_manager.process_request("XLock", 200, "A")  # This will wait

        # Test unlock
        output = lock_manager.process_request("Unlock", 100, "A")
        assert "Unlock 100 A: Lock released" in output
        assert "X-Lock granted to 200" in output
        assert ("A", "X") in [(k, v)
                              for k, v in lock_manager.held_locks[200].items()]

    def test_unlock_end_transaction(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)
        lock_manager.process_request("SLock", 100, "A")
        lock_manager.process_request("Start", 200)
        lock_manager.process_request("XLock", 200, "A")  # This will wait

        # Test unlock
        output = lock_manager.process_request("End", 100)
        assert "End 100 : Transaction 100 ended" in output
        assert "Release S-lock on A" in output
        assert "X-Lock granted to 200" in output
        assert ("A", "X") in [(k, v)
                              for k, v in lock_manager.held_locks[200].items()]
        assert 100 not in lock_manager.transactions
        assert "A" not in lock_manager.held_locks.get(100, {})

    def test_fifo_waiting_policy(self, lock_manager):
        # Setup
        lock_manager.process_request("Start", 100)
        lock_manager.process_request("Start", 200)
        lock_manager.process_request("Start", 300)
        lock_manager.process_request("XLock", 100, "A")

        # Request locks that will wait
        lock_manager.process_request("SLock", 200, "A")
        lock_manager.process_request("SLock", 300, "A")

        # Release lock - should go to 200 first (FIFO)
        output = lock_manager.process_request("Unlock", 100, "A")
        assert "S-Lock granted to 200" in output
        assert "S-Lock granted to 300" not in output  # Only one should be granted

        # Release again - should go to 300
        output = lock_manager.process_request("Unlock", 200, "A")
        assert "S-Lock granted to 300" in output

    def test_complex_scenario(self, lock_manager):
        # Test the exact scenario from the problem statement
        outputs = []
        outputs.append(lock_manager.process_request("Start", 100))
        outputs.append(lock_manager.process_request("Start", 200))
        outputs.append(lock_manager.process_request("SLock", 100, "A"))
        outputs.append(lock_manager.process_request("XLock", 200, "A"))
        outputs.append(lock_manager.process_request("Unlock", 100, "A"))
        outputs.append(lock_manager.process_request("XLock", 100, "B"))
        outputs.append(lock_manager.process_request("XLock", 200, "B"))
        outputs.append(lock_manager.process_request("XLock", 100, "A"))
        outputs.append(lock_manager.process_request("End", 100))
        outputs.append(lock_manager.process_request("Unlock", 200, "A"))
        outputs.append(lock_manager.process_request("End", 200))

        # Verify key outputs
        assert "Transaction 100 started" in outputs[0]
        assert "Lock granted" in outputs[2]
        assert "Waiting for lock" in outputs[3]
        assert "X-Lock granted to 200" in outputs[4]
        assert "X-Lock on B granted to 200" in outputs[8]
        assert "Transaction 200 ended" in outputs[10]

    def test_invalid_requests(self, lock_manager):
        # Test lock requests for non-existent transactions
        assert "not found" in lock_manager.process_request("SLock", 100, "A")
        assert "not found" in lock_manager.process_request("XLock", 100, "A")
        assert "not found" in lock_manager.process_request("Unlock", 100, "A")

        # Test invalid request types
        with pytest.raises(IndexError):
            lock_manager.process_request("Invalid", 100)

        # Test invalid request types
        with pytest.raises(IndexError):
            lock_manager.process_request("Invalid", 100, "A")

import pytest
from lock_manager import simple

class TestSimple:
    """Test of the simple module"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Run before and after each test"""
        # Setup code
        yield
        # Teardown code
   
    def test_null_sum(self):
        """This function test that the function return 0 when the arguments are 0s"""
        assert simple.sum(0,0) == 0
    

    def test_good_sum(self):
        """This function test that the function sum behaves well"""
        assert simple.sum(1,2) == 3
    
    
    @pytest.mark.parametrize("in_a,in_b,expected", [
        (1, 2, 3),
        (2, 4, 6),
        (-1, 0, -1),
        (-1,-2,-3)
    ])
    def test_sum_with_parameters(self, in_a, in_b, expected):
        """The same as test_good_sum but with parameters"""
        assert simple.sum(in_a, in_b) == expected
    
    @pytest.mark.skip(reason="Not implemented yet")
    def test_skipped(self):
        """This test will be skipped"""
        pass
    
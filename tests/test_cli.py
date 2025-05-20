import pytest
from io import StringIO
from unittest.mock import patch
from cli.simple import stream_processor

def test_processor_basic_operation():
    """Test basic line processing functionality."""
    test_input = StringIO("line1\nline2\n")
    test_output = StringIO()
    test_error = StringIO()
    
    with patch('lock_manager.LockManager.process_request_str') as mock_process:
        mock_process.side_effect = lambda line: f"processed_{line}"
        
        stream_processor(test_input, test_output, test_error)
        
        assert test_output.getvalue() == "processed_line1\nprocessed_line2\n"
        assert test_error.getvalue() == ""

def test_processor_empty_input():
    """Test behavior with empty input."""
    test_input = StringIO("")
    test_output = StringIO()
    test_error = StringIO()
    
    with patch('lock_manager.LockManager.process_request_str'):
        stream_processor(test_input, test_output, test_error)
        assert test_output.getvalue() == ""
        assert test_error.getvalue() == ""

def test_processor_error_handling():
    """Test error handling during processing."""
    test_input = StringIO("good\nbad\ngood\n")
    test_output = StringIO()
    test_error = StringIO()
    
    def mock_process(line):
        if line == "bad":
            raise ValueError("Test error")
        return f"processed_{line}"
    
    with patch('lock_manager.LockManager.process_request_str', side_effect=mock_process):
        stream_processor(test_input, test_output, test_error)
        
        assert "processed_good" in test_output.getvalue()
        assert "Test error" in test_error.getvalue()
        assert test_output.getvalue().count("\n") == 2  # Two successful outputs

def test_processor_iterable_output():
    """Test handling of iterable return values from process_line."""
    test_input = StringIO("multi\n")
    test_output = StringIO()
    test_error = StringIO()
    
    with patch('lock_manager.LockManager.process_request_str') as mock_process:
        mock_process.return_value = ["part1", "part2", "part3"]
        
        stream_processor(test_input, test_output, test_error)
        
        assert test_output.getvalue() == "part1\npart2\npart3\n"
import json
from pathlib import Path
from langchain.tools import ToolRuntime, tool
from langgraph.typing import ContextT

from src.agents.thread_state import ThreadState
from src.sandbox.tools import (
    ensure_sandbox_initialized, 
    ensure_thread_directories_exist, 
    is_local_sandbox, 
    get_thread_data, 
    replace_virtual_path, 
    replace_virtual_paths_in_command
)

@tool("read_experiment_metrics", parse_docstring=True)
def read_experiment_metrics(runtime: ToolRuntime[ContextT, ThreadState]) -> str:
    """Read the latest experiment metrics from the Autoresearcher loop.
    
    Returns a JSON string containing the latest val_bpb, peak_vram_gb, and status from the results.
    """
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        ensure_thread_directories_exist(runtime)
        
        # Read results_evobranch.tsv from the workspace
        metrics_file = "/workspace/Autoresearcher/results_evobranch.tsv"
        if is_local_sandbox(runtime):
            metrics_file = replace_virtual_path(metrics_file, get_thread_data(runtime))
            
        content = sandbox.read_file(metrics_file)
        lines = content.strip().split("\n")
        if len(lines) <= 1:
            return json.dumps({"status": "No experiments run yet."})
            
        last_line = lines[-1].split("\t")
        if len(last_line) >= 4:
            return json.dumps({
                "val_bpb": float(last_line[1]),
                "peak_vram_gb": float(last_line[2]),
                "status": last_line[3],
                "description": last_line[4] if len(last_line) > 4 else ""
            })
        return "Error parsing metrics."
    except Exception as e:
        return f"Error: {e}"

@tool("mutate_training_code", parse_docstring=True)
def mutate_training_code(runtime: ToolRuntime[ContextT, ThreadState], new_code: str) -> str:
    """Safely overwrite the train.py script in the Autoresearcher workspace.
    
    Args:
        new_code: The complete, valid Python code to replace train.py with.
    """
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        ensure_thread_directories_exist(runtime)
        
        target_file = "/workspace/Autoresearcher/train.py"
        if is_local_sandbox(runtime):
            target_file = replace_virtual_path(target_file, get_thread_data(runtime))
            
        sandbox.write_file(target_file, new_code)
        return "Successfully mutated train.py"
    except Exception as e:
        return f"Error writing file: {e}"

@tool("trigger_training_cycle", parse_docstring=True)
def trigger_training_cycle(runtime: ToolRuntime[ContextT, ThreadState]) -> str:
    """Execute the Autoresearcher training cycle within the sandbox.
    
    Runs uv run train.py with the correct environment variables for the EvoBranch corpus.
    Takes ~5 minutes. Returns the exit status.
    """
    try:
        sandbox = ensure_sandbox_initialized(runtime)
        ensure_thread_directories_exist(runtime)
        
        cmd = (
            "cd /workspace/Autoresearcher && "
            "AUTORESEARCH_PREPARE_MODULE=prepare_evobranch "
            "AUTORESEARCH_PROFILE=evobranch-tiny "
            "AUTORESEARCH_SAVE_CHECKPOINT=1 "
            "AUTORESEARCH_OUTPUT_DIR=outputs/evobranch-tiny "
            "uv run train.py > run_evobranch.log 2>&1"
        )
        if is_local_sandbox(runtime):
            cmd = replace_virtual_paths_in_command(cmd, get_thread_data(runtime))
            
        result = sandbox.execute_command(cmd)
        
        return f"Training cycle completed.\nSandbox Output: {result}"
    except Exception as e:
        return f"Error executing training cycle: {e}"

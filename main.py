import argparse
import sys
from pathlib import Path

from cache_calculations import calculate_cache
from memory_calculations import calculate_memory
from output import write_results

from page_table import PageTable
from physical_memory import PhysicalMemory
from trace_reader import read_trace


TEAM_NUMBER = "13"


def parse_time_slice(value):
    try:
        number = int(value)

        if number == -1 or number > 0:
            return number

        raise argparse.ArgumentTypeError(
            "Time slice must be -1 or a positive integer."
        )

    except ValueError:
        raise argparse.ArgumentTypeError(
            "Time slice must be an integer."
        )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Simulate virtual memory and calculate cache and physical-memory values."
    )

    parser.add_argument(
        "-s", "--cache-size",
        type=int,
        required=True,
        help="Cache size in KB"
    )

    parser.add_argument(
        "-b", "--block-size",
        type=int,
        required=True,
        help="Cache block size in bytes"
    )

    parser.add_argument(
        "-a", "--associativity",
        type=int,
        required=True,
        help="Cache associativity"
    )

    parser.add_argument(
        "-r", "--replacement",
        choices=["RR", "RND"],
        required=True,
        help="Cache replacement policy"
    )

    parser.add_argument(
        "-p", "--physical-memory",
        type=int,
        required=True,
        help="Physical memory size in MB"
    )

    parser.add_argument(
        "-u", "--os-percent",
        type=float,
        required=True,
        help="Percentage of physical memory reserved for the OS"
    )

    parser.add_argument(
        "-n", "--time-slice",
        type=parse_time_slice,
        required=True,
        help="Instructions per time slice; use -1 for all instructions"
    )

    parser.add_argument(
        "-f", "--trace",
        action="append",
        required=True,
        help="Trace file (provide 1 to 3 trace files)"
    )

    parser.add_argument(
        "--run",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="Simulation output run number: 1, 2, or 3"
    )

    return parser


def validate_arguments(args):
    if args.cache_size <= 0:
        raise ValueError("Cache size must be positive.")

    if args.block_size <= 0:
        raise ValueError("Block size must be positive.")

    if args.associativity <= 0:
        raise ValueError("Associativity must be positive.")

    if args.physical_memory <= 0:
        raise ValueError("Physical memory must be positive.")

    if not 0 <= args.os_percent <= 100:
        raise ValueError("OS percentage must be between 0 and 100.")

    if not 1 <= len(args.trace) <= 3:
        raise ValueError("Provide between 1 and 3 trace files.")

    for trace_file in args.trace:
        if not Path(trace_file).is_file():
            raise FileNotFoundError(
                f"Trace file not found: {trace_file}"
            )


def initialize_statistics():
    return {
        "virtual_pages_mapped": 0,
        "page_table_hits": 0,
        "pages_from_free": 0,
        "total_page_faults": 0
    }


def initialize_processes(trace_files):
    processes = []

    for process_id, trace_file in enumerate(trace_files):
        page_table = PageTable(process_id)

        process = {
            "process_id": process_id,
            "trace_file": trace_file,
            "instruction_iterator": iter(read_trace(trace_file)),
            "page_table": page_table,
            "instructions_processed": 0,
            "finished": False,
            "final_page_table_usage": None
        }

        processes.append(process)

    return processes


def process_memory_access(
    process,
    processes,
    address,
    physical_memory,
    statistics
):
    if address is None or address == 0:
        return

    virtual_page = address // 4096

    page_table = process["page_table"]

    statistics["virtual_pages_mapped"] += 1

    physical_page = page_table.lookup(virtual_page)

    if physical_page is not None:
        statistics["page_table_hits"] += 1
        return

    allocation = physical_memory.allocate(
        process["process_id"],
        virtual_page
    )

    physical_page = allocation["physical_page"]

    evicted_process_id = allocation.get("evicted_process_id")
    evicted_virtual_page = allocation.get("evicted_virtual_page")

    if evicted_process_id is None:
        statistics["pages_from_free"] += 1

    else:
        statistics["total_page_faults"] += 1

        for old_process in processes:
            if old_process["process_id"] == evicted_process_id:
                old_process["page_table"].unmap_page(
                    evicted_virtual_page
                )
                break

    page_table.map_page(
        virtual_page,
        physical_page
    )


def process_instruction(
    process,
    processes,
    instruction,
    physical_memory,
    statistics
):
    # Process the instruction address.
    process_memory_access(
        process,
        processes,
        instruction.get("eip"),
        physical_memory,
        statistics
    )

    # Process the destination memory address.
    process_memory_access(
        process,
        processes,
        instruction.get("dst"),
        physical_memory,
        statistics
    )

    # Process the source memory address.
    process_memory_access(
        process,
        processes,
        instruction.get("src"),
        physical_memory,
        statistics
    )

    process["instructions_processed"] += 1


def finish_process(process, physical_memory):
    # Save page table usage before releasing physical memory.
    process["final_page_table_usage"] = (
        process["page_table"].get_usage()
    )

    # Release all physical pages belonging to this process.
    physical_memory.free_process(
        process["process_id"]
    )

    process["finished"] = True


def run_scheduler(
    processes,
    instructions_per_time_slice,
    physical_memory,
    statistics
):
    while any(not process["finished"] for process in processes):

        for process in processes:

            if process["finished"]:
                continue

            instructions_executed = 0

            while (
                instructions_per_time_slice == -1
                or instructions_executed < instructions_per_time_slice
            ):

                try:
                    instruction = next(
                        process["instruction_iterator"]
                    )

                except StopIteration:
                    finish_process(
                        process,
                        physical_memory
                    )
                    break

                process_instruction(
                    process,
                    processes,
                    instruction,
                    physical_memory,
                    statistics
                )

                instructions_executed += 1

            if not process["finished"]:
                continue


def calculate_process_usage(processes, memory_results):
    process_usage = []

    entries_per_process = memory_results.get(
        "page_table_entries_per_process",
        512 * 1024
    )

    entry_bits = memory_results["page_table_entry_bits"]

    total_table_bytes = (
        entries_per_process * entry_bits
    ) / 8

    for process in processes:

        usage = process["final_page_table_usage"]

        used_entries = usage["used_entries"]

        used_bytes = (
            used_entries * entry_bits
        ) / 8

        wasted_bytes = total_table_bytes - used_bytes

        process_usage.append({
            "process_id": process["process_id"],
            "used_page_table_entries": used_entries,
            "page_table_wasted": wasted_bytes
        })

    return process_usage


def append_m2_results(
    output_file,
    memory_results,
    statistics,
    process_usage
):
    with open(output_file, "a", encoding="utf-8") as file:

        file.write("\n")
        file.write("MILESTONE 2 - VIRTUAL MEMORY RESULTS\n")
        file.write("-------------------------------------\n")

        file.write(
            f"Physical Pages Used By SYSTEM: "
            f"{memory_results['os_reserved_pages']}\n"
        )

        file.write(
            f"Pages Available to User: "
            f"{memory_results['user_available_pages']}\n"
        )

        file.write(
            f"Virtual Pages Mapped: "
            f"{statistics['virtual_pages_mapped']}\n"
        )

        file.write(
            f"Page Table Hits: "
            f"{statistics['page_table_hits']}\n"
        )

        file.write(
            f"Pages from Free: "
            f"{statistics['pages_from_free']}\n"
        )

        file.write(
            f"Total Page Faults: "
            f"{statistics['total_page_faults']}\n"
        )

        file.write("\n")
        file.write("PAGE TABLE USAGE PER PROCESS\n")
        file.write("----------------------------\n")

        for usage in process_usage:

            file.write(
                f"Process {usage['process_id'] + 1}:\n"
            )

            file.write(
                f"Used Page Table Entries: "
                f"{usage['used_page_table_entries']}\n"
            )

            file.write(
                f"Page Table Wasted: "
                f"{usage['page_table_wasted']:.2f} bytes\n"
            )

            file.write("\n")


def run_simulation(args):
    validate_arguments(args)

    # Calculate the Milestone 1 cache results.
    cache_results = calculate_cache(
        cache_size_kb=args.cache_size,
        block_size=args.block_size,
        associativity=args.associativity,
        physical_memory_mb=args.physical_memory
    )

    # Calculate the Milestone 1 memory results.
    memory_results = calculate_memory(
        physical_memory_mb=args.physical_memory,
        os_percent=args.os_percent,
        num_processes=len(args.trace)
    )

    # Initialize physical memory.
    physical_memory = PhysicalMemory(
        total_pages=memory_results["total_physical_pages"],
        system_pages=memory_results["os_reserved_pages"],
        replacement_policy=args.replacement
    )

    # Initialize processes and their page tables.
    processes = initialize_processes(args.trace)

    # Initialize virtual memory statistics.
    statistics = initialize_statistics()

    # Run the process scheduler.
    run_scheduler(
        processes,
        args.time_slice,
        physical_memory,
        statistics
    )

    # Calculate page table usage for each process.
    process_usage = calculate_process_usage(
        processes,
        memory_results
    )

    # Prepare the original Milestone 1 output.
    inputs = {
        "cache_size_kb": args.cache_size,
        "block_size": args.block_size,
        "associativity": args.associativity,
        "replacement_policy": args.replacement,
        "physical_memory_mb": args.physical_memory,
        "os_percent": args.os_percent,
        "instructions_per_time_slice": args.time_slice
    }

    output_directory = "output"

    output_file = write_results(
        team_number=TEAM_NUMBER,
        trace_files=args.trace,
        inputs=inputs,
        cache_results=cache_results,
        memory_results=memory_results,
        run_number=args.run,
        output_directory=output_directory
    )

    # Append the Milestone 2 virtual memory results.
    append_m2_results(
        output_file,
        memory_results,
        statistics,
        process_usage
    )

    print(f"Simulation completed. Output saved to: {output_file}")


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        run_simulation(args)

    except (ValueError, FileNotFoundError, KeyError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()

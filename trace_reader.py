def read_trace(trace_file):
    """
    Generator yielding each instruction from the two-line trace format:
      {
        "eip": int,
        "dst": int or None,
        "src": int or None
      }
    Ignores zero (00000000) or invalid ('--------') data addresses.
    """
    with open(trace_file, "r", encoding="utf-8", errors="ignore") as file:
        while True:
            eip_line = file.readline()
            if not eip_line:
                break
            if not eip_line.startswith("EIP"):
                continue

            data_line = file.readline()
            if not data_line:
                break

           
            eip_addr = int(eip_line[10:18], 16)

            
            dst_addr = None
            if len(data_line) >= 23:
                dst_addr_str = data_line[6:14]
                dst_data_str = data_line[15:23]
                if dst_addr_str != "00000000" and not dst_data_str.startswith("-"):
                    dst_addr = int(dst_addr_str, 16)

            src_addr = None
            if len(data_line) >= 50:
                src_addr_str = data_line[33:41]
                src_data_str = data_line[42:50]
                if src_addr_str != "00000000" and not src_data_str.startswith("-"):
                    src_addr = int(src_addr_str, 16)

            yield {
                "eip": eip_addr,
                "dst": dst_addr,
                "src": src_addr,
            }

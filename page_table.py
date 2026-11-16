class PageTable:
    def __init__(self, process_id):
        self.process_id = process_id
        self.entries = {}
        self.ever_used = set()

    def _check_virtual_page(self, virtual_page):
        if not 0 <= virtual_page < 524288:
            raise ValueError(f"Process {self.process_id}: virtual page {virtual_page:#x} is outside the page table (0 to {524287:#x})")

    def lookup(self, virtual_page):
        return self.entries.get(virtual_page) # this returns the physical page mapped to virtual_page, and None if it is'nt mapped.

    def map_page(self, virtual_page, physical_page):
        self._check_virtual_page(virtual_page)

        if physical_page is None or physical_page < 0:
            raise ValueError(f"Process {self.process_id}: invalid physical page {physical_page} for virtual page {virtual_page:#x}")

        self.entries[virtual_page] = physical_page
        self.ever_used.add(virtual_page)

    def unmap_page(self, virtual_page):
        return self.entries.pop(virtual_page, None)

    def get_usage(self):
        used_entries = len(self.ever_used)

        return {
            "used_entries": used_entries,
            "currently_mapped": len(self.entries),
            "wasted_entries": 524288 - used_entries,
            "used_percent": used_entries * 100 / 524288,
        }
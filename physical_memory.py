"""Milestone 2: manage physical pages for the virtual memory simulator.

Physical pages reserved for the operating system are never assigned to users.
"""

import random


class PhysicalMemory:
    def __init__(self, total_pages, system_pages, replacement_policy):
        if total_pages <= 0 or not 0 <= system_pages <= total_pages:
            raise ValueError("Invalid physical or system page count")

        self.total_pages = total_pages
        self.system_pages = system_pages
        self.replacement_policy = replacement_policy.upper()

        if self.replacement_policy not in ("RR", "RND"):
            raise ValueError("Replacement policy must be RR or RND")


        self.page_owners = {}


        self.process_pages = {}

        self.next_free_page = system_pages
        self.released_pages = []
        self.next_victim = system_pages

        self.pages_from_free = 0
        self.page_faults = 0

    def allocate(self, process_id, virtual_page):

        pages = self.process_pages.get(process_id, {})


        if virtual_page in pages:
            return {
                "physical_page": pages[virtual_page],
                "evicted_process_id": None,
                "evicted_virtual_page": None,
            }

        evicted_process_id = None
        evicted_virtual_page = None

        if self.released_pages:

            physical_page = self.released_pages.pop()
            self.pages_from_free += 1
        elif self.next_free_page < self.total_pages:

            physical_page = self.next_free_page
            self.next_free_page += 1
            self.pages_from_free += 1
        else:

            if self.system_pages == self.total_pages:
                raise ValueError("No physical pages available for user processes")

            if self.replacement_policy == "RND":
                physical_page = random.randrange(self.system_pages, self.total_pages)
            else:
                physical_page = self.next_victim
                self.next_victim += 1
                if self.next_victim == self.total_pages:
                    self.next_victim = self.system_pages

            evicted_process_id, evicted_virtual_page = self.page_owners[physical_page]


            del self.process_pages[evicted_process_id][evicted_virtual_page]
            if not self.process_pages[evicted_process_id]:
                del self.process_pages[evicted_process_id]
            self.page_faults += 1


        self.page_owners[physical_page] = (process_id, virtual_page)
        self.process_pages.setdefault(process_id, {})[virtual_page] = physical_page

        return {
            "physical_page": physical_page,
            "evicted_process_id": evicted_process_id,
            "evicted_virtual_page": evicted_virtual_page,
        }

    def free_process(self, process_id):
        
        pages = self.process_pages.pop(process_id, {})
        freed_pages = []

        for physical_page in pages.values():
            del self.page_owners[physical_page]
            self.released_pages.append(physical_page)
            freed_pages.append(physical_page)

        return freed_pages

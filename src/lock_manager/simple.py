import re


class LockManager:

    held_locks = {}
    transactions = []

    def process_request(self, request: str, transaction: int, resource: str = None) -> list[str]:

        return ["Not implemented :("]

    def process_request_str(self, request_str: str) -> list[str]:

        # Using regex groups
        pattern = r"(\w+) (\d+) ?(\w*)"
        match = re.search(pattern, request_str)

        if match:
            request, transaction, resource = match.groups()
            return self.process_request(request, transaction, resource)
        else:
            raise ValueError(
                f"Text '{request_str}' doesn't match expected format: request transaction <resource>")

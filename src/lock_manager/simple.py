import re
from dataclasses import dataclass


@dataclass
class Command:
    cmd: str
    transaction: int = None
    resource: str = None


class LockManager:

    held_locks = {}
    transactions = []

    def process_request(self, request: str, transaction: int, resource: str = None) -> list[Command]:

        return [Command('not_implemented')]

    def commands_mapping(self, cmd: Command):
        mapping = {'not_implemented': lambda t, r: "Not implemented :("}
        return mapping[cmd.cmd](cmd.transaction, cmd.resource)

    def process_request_str(self, request_str: str) -> list[str]:

        # Using regex groups
        pattern = r"(\w+) (\d+) ?(\w*)"
        match = re.search(pattern, request_str)

        if match:
            request, transaction, resource = match.groups()
            outs = self.process_request(request, transaction, resource)
            return "\n".join([self.commands_mapping(out) for out in outs])
        else:
            raise ValueError(
                f"Text '{request_str}' doesn't match expected format: request transaction <resource>")

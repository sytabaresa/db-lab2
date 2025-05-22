import re
from dataclasses import dataclass
from enum import Enum


class Events(Enum):
    SLOCK = 'SLock'
    XLOCK = 'XLock'
    UNLOCK = 'Unlock'
    START = 'Start'
    END = 'End'


class States(Enum):
    slock = 'slock'
    xlock = 'xlock'


@dataclass
class Command:
    cmd: str
    transaction: int = None
    resource: str = None
    lock_type: States = None
    extra: dict = None


class LockManager:

    def __init__(self):
        self.held_locks = {}
        self.transactions = []
        self.resource_fifo = {}

    def process_request(self, request: str, transaction: int, resource: str = None) -> list[Command]:
        """Business logic, based in transaction and resource FSMs"""
        try:
            req = Events(request)
        except ValueError:
            raise IndexError("Command not valid")
        cmds = []

        # Transaction FSM
        if not resource:
            # not_init state
            if transaction not in self.transactions:
                if req is Events.START:
                    self.transactions.append(transaction)
                    cmds.append(Command('transaction_started', transaction))
                elif req is Events.END:
                    raise ValueError(
                        f"Transaction {transaction} not started")
            # init state
            elif transaction in self.transactions:
                if req is Events.END:
                    cmds.append(Command('transaction_ended', transaction))

                    # Unlock all resources that this transaction locks
                    locked_resources = list(
                        self.held_locks.get(transaction, {}).keys())
                    for r in locked_resources:
                        _cmds = self.process_request(
                            Events.UNLOCK, transaction, r)
                        if 0 < len(_cmds):
                            out = _cmds[0]
                            cmds.append(
                                Command(f"release_{out.cmd}", out.transaction, out.resource, out.lock_type))
                        if 1 < len(_cmds):
                            out = _cmds[1]
                            cmds.append(
                                Command(f"resource_{out.cmd}", out.transaction, out.resource, out.lock_type))

                    # Clean waiting locks
                    for xt in self.resource_fifo.values():
                        if xt.get(transaction):
                            del xt[transaction]

                    # Finally remove tracking transaction
                    self.transactions.remove(transaction)
                    if self.held_locks.get(transaction):
                        del self.held_locks[transaction]
                else:
                    raise ValueError(
                        f"Transaction {transaction} already started")
        # Resource FSM
        elif resource:
            if transaction not in self.transactions:
                raise ValueError("Transaction not found")

            # unlock state
            elif not self.resource_state(resource):
                if req is Events.SLOCK:
                    cmds.extend(
                        self.lock_resource(transaction, resource, States.slock))
                elif req is Events.XLOCK:
                    cmds.extend(
                        self.lock_resource(transaction, resource, States.xlock))

            # s-Lock state
            elif self.resource_state(resource) is States.slock:
                if req is Events.SLOCK:
                    if self.held_locks.get(transaction, {}).get(resource):
                        cmds.append(
                            Command('duplicate', transaction, resource, States.slock))
                    else:
                        cmds.extend(
                            self.lock_resource(transaction, resource, States.slock))
                elif req is Events.XLOCK:
                    cmds.extend(
                        self.wait_for_lock(transaction, resource, States.slock, States.xlock))

                elif req is Events.UNLOCK and self.held_locks[transaction][resource] is States.slock:
                    cmds.extend(
                        self.grant_next_lock(transaction, resource, States.slock))

            # x-Lock state
            elif self.resource_state(resource) is States.xlock:
                if req is Events.SLOCK:
                    cmds.extend(
                        self.wait_for_lock(transaction, resource, States.xlock, States.slock))

                elif req is Events.XLOCK:
                    if self.held_locks.get(transaction, {}).get(resource):
                        cmds.append(
                            Command('duplicate', transaction, resource, States.xlock))
                    else:
                        cmds.extend(
                            self.wait_for_lock(transaction, resource, States.xlock, States.xlock))

                if req is Events.UNLOCK and self.held_locks[transaction][resource] is States.xlock:
                    cmds.extend(
                        self.grant_next_lock(transaction, resource, States.xlock))
        return cmds

    def commands_mapping(self, cmd: Command):
        """Out Adapter for the commands returned from business logic"""
        mapping = {
            'transaction_started': lambda cmd: f"Start {cmd.transaction} : Transaction {cmd.transaction} started",
            'transaction_ended': lambda cmd: f"End {cmd.transaction} : Transaction {cmd.transaction} ended",
            'granted': lambda cmd: f"{'SLock' if cmd.lock_type is States.slock else 'XLock'} {cmd.transaction} {cmd.resource}: Lock granted",
            'granted_to': lambda cmd: f"{'S-Lock' if cmd.lock_type is States.slock else 'X-Lock'} granted to {cmd.transaction}",
            'resource_granted_to': lambda cmd: f"{'S-Lock' if cmd.lock_type is States.slock else 'X-Lock'} on {cmd.resource} granted to {cmd.transaction}",
            'unlocked': lambda cmd: f"Unlock {cmd.transaction} {cmd.resource}: Lock released",
            'duplicate': lambda cmd: f"{'SLock' if cmd.lock_type is States.slock else 'XLock'} {cmd.transaction} {cmd.resource}: Lock already held",
            'release_unlocked': lambda cmd: f"Release {'S-lock' if cmd.lock_type is States.slock else 'X-lock'} on {cmd.resource}",
            "waiting": lambda cmd: f"{'SLock' if cmd.lock_type is States.slock else 'XLock'} {cmd.transaction} {cmd.resource}: " +
            f"Waiting for lock ({'S-lock' if cmd.extra['lock_type'] is States.slock else 'X-lock'} held by: {cmd.extra['transaction']})",
        }
        
        return mapping[cmd.cmd](cmd)


    def resource_state(self, resource: str) -> States:
        transactions = list(self.resource_fifo.get(resource, {}).values())
        if len(transactions) > 0:
            return transactions[0]

    def lock_resource(self, transaction: int, resource: str, lock_type: States):
        self.held_locks.setdefault(transaction, {})[
            resource] = lock_type
        self.resource_fifo.setdefault(
            resource, {})[transaction] = lock_type
        return [Command("granted", transaction, resource, lock_type)]

    def wait_for_lock(self, transaction: int, resource: str, old_lock_type: States, next_lock_type: States):
        old_transaction = list(
            self.resource_fifo[resource].keys())[0]
        self.resource_fifo[resource][transaction] = next_lock_type

        return [Command("waiting",
                        transaction, resource, next_lock_type,
                        extra={'lock_type': old_lock_type, 'transaction': old_transaction})]

    def grant_next_lock(self, transaction: int, resource: str, lock_type: States):
        cmds = []

        del self.held_locks[transaction][resource]
        del self.resource_fifo[resource][transaction]

        cmds.append(Command('unlocked', transaction, resource, lock_type))

        next_transactions = list(
            self.resource_fifo[resource].keys())
        if len(next_transactions) > 0:
            next_transaction = next_transactions[0]
            lock_type = self.resource_fifo[resource][next_transaction]

            self.held_locks.setdefault(next_transaction, {})[
                resource] = lock_type
            cmds.append(
                Command("granted_to", next_transaction, resource, lock_type))

        return cmds

    def process_request_str(self, request_str: str) -> list[str]:
        """Adapter for business logic, IN/OUT conversion"""
        # Using regex groups
        pattern = r"^(\w+) (\d+) ?(\w+)?_*$"
        match = re.search(pattern, request_str)

        if match:
            request, transaction, resource = match.groups()
            outs = self.process_request(request, int(transaction), resource)
            # Joining commands in newlines
            return "\n".join([self.commands_mapping(out) for out in outs])
        else:
            raise IndexError(
                f"Text '{request_str}' doesn't match expected format: request transaction <resource>")

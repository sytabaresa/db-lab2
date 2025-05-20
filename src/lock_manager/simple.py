import re
from dataclasses import dataclass
from enum import Enum, auto


class Events(Enum):
    SLOCK = 'SLock'
    XLOCK = 'XLock'
    UNLOCK = 'Unlock'
    START = 'Start'
    END = 'End'


class States(Enum):
    slock = 'S',
    xlock = 'X'


@dataclass
class Command:
    cmd: str
    transaction: int = None
    resource: str = None
    extra: dict = None


class LockManager:

    def __init__(self):
        self.held_locks = {}
        self.transactions = []
        self.resource_fifo = {}

    def resource_state(self, resource) -> States:
        transactions = list(self.resource_fifo.get(resource, {}).values())
        if len(transactions) > 0:
            return transactions[0]

    def lock_resource(self, transaction, resource, lock_type):
        self.held_locks.setdefault(transaction, {})[
            resource] = lock_type
        self.resource_fifo.setdefault(
            resource, {})[transaction] = lock_type
        return [Command('slocked' if lock_type is States.slock else 'xlocked', transaction, resource)]

    def wait_for_lock(self, transaction, resource, old_lock_type, next_lock_type):
        old_transaction = list(
            self.resource_fifo[resource].keys())[0]
        self.resource_fifo[resource][transaction] = next_lock_type

        return [Command('waiting_slock' if next_lock_type is States.slock else 'waiting_xlock',
                        transaction, resource,
                        extra={'lock_type': old_lock_type, 'transaction': old_transaction})]

    def grant_next_lock(self, transaction, resource, lock_type):
        cmds = []

        del self.held_locks[transaction][resource]
        del self.resource_fifo[resource][transaction]

        cmds.append(Command(
            'sunlocked' if lock_type is States.slock else 'xunlocked', transaction, resource))

        next_transactions = list(
            self.resource_fifo[resource].keys())
        if len(next_transactions) > 0:
            next_transaction = next_transactions[0]
            lock_type = self.resource_fifo[resource][next_transaction]

            self.held_locks.setdefault(next_transaction, {})[
                resource] = lock_type
            cmds.append(
                Command('granted_slocked' if lock_type is States.slock else 'granted_xlocked', next_transaction, resource))

        return cmds

    def process_request(self, request: str, transaction: int, resource: str = None) -> list[Command]:
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
                    res = list(self.held_locks.get(transaction, {}).keys())
                    for r in res:
                        _cmds = self.process_request(
                            Events.UNLOCK, transaction, r)
                        if 0 < len(_cmds):
                            out = _cmds[0]
                            cmds.append(
                                Command('release_'+out.cmd, out.transaction, out.resource))
                        if 1 < len(_cmds):
                            out = _cmds[1]
                            cmds.append(
                                Command('resource_'+out.cmd, out.transaction, out.resource))

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
                            Command('slock_already', transaction, resource))
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
                            Command('xlock_already', transaction, resource))
                    else:
                        cmds.extend(
                            self.wait_for_lock(transaction, resource, States.xlock, States.xlock))

                if req is Events.UNLOCK and self.held_locks[transaction][resource] is States.xlock:
                    cmds.extend(
                        self.grant_next_lock(transaction, resource, States.xlock))
        return cmds

    def commands_mapping(self, cmd: Command):
        mapping = {
            'not_implemented': lambda t, r: "Not implemented :(",
            'transaction_started': lambda t, r: f"Start {t} : Transaction {t} started",
            'transaction_ended': lambda t, r: f"End {t} : Transaction {t} ended",
            'slocked': lambda t, r: f"SLock {t} {r}: Lock granted",
            'xlocked': lambda t, r: f"XLock {t} {r}: Lock granted",
            'granted_slocked': lambda t, r: f"S-Lock granted to {t}",
            'granted_xlocked': lambda t, r: f"X-Lock granted to {t}",
            'resource_granted_xlocked': lambda t, r: f"X-Lock on {r} granted to {t}",
            'resource_granted_slocked': lambda t, r: f"S-Lock on {r} granted to {t}",
            'sunlocked': lambda t, r: f"Unlock {t} {r}: Lock released",
            'xunlocked': lambda t, r: f"Unlock {t} {r}: Lock released",
            'slock_already': lambda t, r: f"SLock {t} {r}: Lock already held",
            'xlock_already': lambda t, r: f"XLock {t} {r}: Lock already held",
            'release_sunlocked': lambda t, r: f"Release S-lock on {r}",
            'release_xunlocked': lambda t, r: f"Release X-lock on {r}",
            "waiting_slock": lambda t, r, x: f"SLock {t} {r}: Waiting for lock ({'X-lock' if x['lock_type'] is States.xlock else 'S-lock'} held by: {x['transaction']})",
            "waiting_xlock": lambda t, r, x: f"XLock {t} {r}: Waiting for lock ({'X-lock' if x['lock_type'] is States.xlock else 'S-lock'} held by: {x['transaction']})",
        }
        if cmd.extra:
            return mapping[cmd.cmd](cmd.transaction, cmd.resource, cmd.extra)
        else:
            return mapping[cmd.cmd](cmd.transaction, cmd.resource)

    def process_request_str(self, request_str: str) -> list[str]:

        # Using regex groups
        pattern = r"^(\w+) (\d+) ?(\w+)?_*$"
        match = re.search(pattern, request_str)

        if match:
            request, transaction, resource = match.groups()
            outs = self.process_request(request, int(transaction), resource)
            return "\n".join([self.commands_mapping(out) for out in outs])
        else:
            raise IndexError(
                f"Text '{request_str}' doesn't match expected format: request transaction <resource>")

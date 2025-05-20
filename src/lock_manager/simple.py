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
        self.resource_state = {}

    def process_request(self, request: str, transaction: int, resource: str = None) -> list[Command]:
        try:
            req = Events(request)
        except ValueError:
            raise IndexError("Command not valid")
        cmds = []

        # transaction FSM
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
                    
                    # Unlock all resources that this transaction has
                    res = list(self.held_locks.get(transaction).keys())
                    for r in res:
                        _cmds = self.process_request(
                            Events.UNLOCK, transaction, r)
                        if 0 < len(_cmds):
                            cmds.append(
                                Command('release_'+_cmds[0].cmd, _cmds[0].transaction, _cmds[0].resource))
                        if 1 < len(_cmds):
                            cmds.append(_cmds[1])
                    self.transactions.remove(transaction)
                    del self.held_locks[transaction]
                else:
                    raise ValueError(
                        f"Transaction {transaction} already started")
        # resource FSM
        elif resource:
            if transaction not in self.transactions:
                raise ValueError("Transaction not found")

            # unlock state
            elif not self.resource_state.get(resource):
                if req is Events.SLOCK:
                    self.held_locks.setdefault(transaction, {})[
                        resource] = States.slock
                    self.resource_state[resource] = States.slock
                    self.resource_fifo.setdefault(
                        resource, {})[transaction] = True
                    cmds.append(Command('slocked', transaction, resource))
                elif req is Events.XLOCK:
                    self.held_locks.setdefault(transaction, {})[
                        resource] = States.xlock
                    self.resource_state[resource] = States.xlock
                    self.resource_fifo.setdefault(
                        resource, {})[transaction] = True
                    cmds.append(Command('xlocked', transaction, resource))
            # s-Lock state
            elif self.resource_state[resource] is States.slock:
                if req is Events.SLOCK:
                    if self.held_locks.get(transaction, {}).get(resource):
                        cmds.append(
                            Command('slock_already', transaction, resource))
                    else:
                        self.held_locks.setdefault(transaction, {})[
                            resource] = States.slock
                        self.resource_fifo.setdefault(
                            resource, {})[transaction] = True
                        cmds.append(Command('slocked', transaction, resource))
                elif req is Events.XLOCK:
                    old_transaction = list(
                        self.resource_fifo[resource].keys())[0]
                    old_lock_type = self.held_locks[old_transaction][resource]
                    self.resource_fifo[resource][transaction] = True
                    self.held_locks.setdefault(transaction, {})[
                        resource] = States.xlock

                    cmds.append(Command('waiting_xlock',
                                transaction, resource, extra={'lock_type': old_lock_type, 'transaction': old_transaction}))

                elif req is Events.UNLOCK and self.held_locks[transaction][resource] is States.slock:
                    # TODO: grant lock
                    del self.held_locks[transaction][resource]
                    del self.resource_fifo[resource][transaction]
                    cmds.append(Command('sunlocked', transaction, resource))

                    del self.resource_state[resource]

                    next = list(self.resource_fifo[resource].keys())
                    if len(next) > 0:
                        next_transaction = next[0]
                        lock_type = self.held_locks[next_transaction][resource]
                        _cmds = self.process_request(
                            Events.SLOCK if lock_type is States.slock else Events.XLOCK, next_transaction, resource)
                        cmds.append(
                            Command("granted_"+_cmds[0].cmd, _cmds[0].transaction, _cmds[0].resource))
            # x-Lock state
            elif self.resource_state[resource] is States.xlock:
                if req is Events.SLOCK:
                    old_transaction = list(
                        self.resource_fifo[resource].keys())[0]
                    old_lock_type = self.held_locks[old_transaction][resource]
                    self.resource_fifo[resource][transaction] = True
                    self.held_locks.setdefault(transaction, {})[
                        resource] = States.slock

                    cmds.append(Command('waiting_slock',
                                transaction, resource, extra={'lock_type': old_lock_type, 'transaction': old_transaction}))

                elif req is Events.XLOCK:
                    if self.held_locks.get(transaction, {}).get(resource):
                        cmds.append(
                            Command('xlock_already', transaction, resource))
                    else:
                        old_transaction = list(
                            self.resource_fifo[resource].keys())[0]
                        old_lock_type = self.held_locks[old_transaction][resource]
                        self.held_locks.setdefault(transaction, {})[
                            resource] = States.xlock
                        cmds.append(Command('waiting_xlock',
                                            transaction, resource, extra={'lock_type': old_lock_type, 'transaction': old_transaction}))

                        self.resource_fifo[resource][transaction] = True
                        self.held_locks.setdefault(transaction, {})[
                            resource] = States.xlock

                if req is Events.UNLOCK and self.held_locks[transaction][resource] is States.xlock:
                    del self.held_locks[transaction][resource]
                    del self.resource_fifo[resource][transaction]
                    cmds.append(Command('xunlocked', transaction, resource))

                    del self.resource_state[resource]

                    next = list(self.resource_fifo[resource].keys())
                    if len(next) > 0:
                        next_transaction = next[0]
                        lock_type = self.held_locks[next_transaction][resource]
                        _cmds = self.process_request(
                            Events.SLOCK if lock_type is States.slock else Events.XLOCK, next_transaction, resource)
                        cmds.append(
                            Command("granted_"+_cmds[0].cmd, _cmds[0].transaction, _cmds[0].resource))
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

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
    slock = 'slocked'
    xlock = 'xlocked'


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
        self.held_resources = {}

    def process_request(self, request: str, transaction: int, resource: str = None) -> list[Command]:
        """Business logic, based in transaction and resource FSMs"""
        cmds = []
        try:
            req = Events(request)
        except ValueError:
            return [Command("cmd_not_valid", transaction, resource)]

        # Transaction FSM
        if not resource:
            # not_init state
            if transaction not in self.transactions:
                if req is Events.START:
                    self.transactions.append(transaction)
                    cmds.append(Command('transaction_started', transaction))
                elif req is Events.END:
                    return [Command('not_started', transaction, resource)]
            # init state
            elif transaction in self.transactions:
                if req is Events.END:
                    cmds.append(Command('transaction_ended', transaction))

                    # Unlock all resources that this transaction holds
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
                    return [Command('already_started', transaction, resource)]
        # Resource FSM
        elif resource:
            if transaction not in self.transactions:
                return [Command("not_found", transaction, resource)]

            # unlock state
            elif not self.resource_state(resource):
                if req is Events.SLOCK:
                    cmds.extend(
                        self.lock_resource(transaction, resource, States.slock))
                elif req is Events.XLOCK:
                    cmds.extend(
                        self.lock_resource(transaction, resource, States.xlock))
                elif req is Events.UNLOCK:
                    cmds.append(
                        Command('not_locked', transaction, resource))
            # s-Lock state
            elif self.resource_state(resource)[0][1] is States.slock:
                if req is Events.SLOCK:
                    if self.held_resources.get(resource, {}).get(transaction):
                        cmds.append(
                            Command('already_held', transaction, resource, States.slock))
                    else:
                        cmds.extend(
                            self.lock_resource(transaction, resource, States.slock))
                elif req is Events.XLOCK:
                    if self.held_resources.get(resource, {}).get(transaction):
                        if len(self.resource_state(resource)) < 2:
                            self.held_locks[transaction][resource] = States.xlock
                            self.held_resources[resource][transaction] = States.xlock
                            cmds.append(
                                Command('upgrade', transaction, resource))
                        else:
                            cmds.extend(
                                self.wait_for_lock_upgrade(transaction, resource, States.slock, States.xlock))
                    else:
                        cmds.extend(
                            self.wait_for_lock(transaction, resource, States.slock, States.xlock))
                elif req is Events.UNLOCK:
                    if self.held_resources.get(resource, {}).get(transaction) is States.slock:
                        cmds.extend(
                            self.unlock(transaction, resource, States.slock))
                        cmds.extend(
                            self.grant_next_locks(resource))
                    else:
                        cmds.append(
                            Command('not_locked_by', transaction, resource))
            # x-Lock state
            elif self.resource_state(resource)[0][1] is States.xlock:
                if req is Events.SLOCK:
                    if self.held_resources.get(resource, {}).get(transaction):
                        cmds.append(
                            Command('already_held', transaction, resource, States.slock))
                    else:
                        cmds.extend(
                            self.wait_for_lock(transaction, resource, States.xlock, States.slock))
                elif req is Events.XLOCK:
                    if self.held_resources.get(resource, {}).get(transaction):
                        cmds.append(
                            Command('already_held', transaction, resource, States.xlock))
                    else:
                        cmds.extend(
                            self.wait_for_lock(transaction, resource, States.xlock, States.xlock))

                if req is Events.UNLOCK:
                    if self.held_resources.get(resource, {}).get(transaction) is States.xlock:
                        cmds.extend(
                            self.unlock(transaction, resource, States.xlock))
                        cmds.extend(
                            self.grant_next_locks(resource))
                    else:
                        cmds.append(
                            Command('not_locked_by', transaction, resource))
        return cmds

    def commands_mapping(self, cmd: Command):
        """Out Adapter for the commands returned from business logic"""
        mapping = {
            'cmd_not_valid': lambda cmd: IndexError("Command not valid"),
            'transaction_started': lambda cmd: f"Start {cmd.transaction} : Transaction {cmd.transaction} started",
            'transaction_ended': lambda cmd: f"End {cmd.transaction} : Transaction {cmd.transaction} ended",
            'not_started': lambda cmd: ValueError(f"Transaction {cmd.transaction} not started"),
            'already_started': lambda cmd: ValueError(f"Transaction {cmd.transaction} already started"),
            'not_found': lambda cmd: ValueError("Transaction not found"),
            'granted': lambda cmd: f"{'SLock' if cmd.lock_type is States.slock else 'XLock'} {cmd.transaction} {cmd.resource}: Lock granted",
            'granted_to': lambda cmd: f"{'S-Lock' if cmd.lock_type is States.slock else 'X-Lock'} granted to {cmd.transaction}",
            'upgrade': lambda cmd: f"Upgraded to XL granted",
            'upgrade_to': lambda cmd: f"Upgraded to XL granted to {cmd.transaction}",
            'waiting_upgrade': lambda cmd: f"Waiting for lock upgrade (S-lock held by: {cmd.extra['transaction']})",
            'resource_granted_to': lambda cmd: f"{'S-Lock' if cmd.lock_type is States.slock else 'X-Lock'} on {cmd.resource} granted to {cmd.transaction}",
            'unlocked': lambda cmd: f"Unlock {cmd.transaction} {cmd.resource}: Lock released",
            'already_held': lambda cmd: ValueError(f"{'SLock' if cmd.lock_type is States.slock else 'XLock'} {cmd.transaction} {cmd.resource}: Lock already held"),
            'release_unlocked': lambda cmd: f"Release {'S-lock' if cmd.lock_type is States.slock else 'X-lock'} on {cmd.resource}",
            'not_locked': lambda cmd: ValueError(f"Cannot unlock {cmd.resource}, not locked"),
            'not_locked_by': lambda cmd: ValueError(f"Cannot unlock {cmd.resource}, not locked by this transaction"),
            "waiting": lambda cmd: f"{'SLock' if cmd.lock_type is States.slock else 'XLock'} {cmd.transaction} {cmd.resource}: " +
            f"Waiting for lock ({'S-lock' if cmd.extra['lock_type'] is States.slock else 'X-lock'} held by: {cmd.extra['transaction']})",
        }

        out_cmd = mapping[cmd.cmd](cmd)
        if isinstance(out_cmd, Exception):
            raise out_cmd
        else:
            return out_cmd

    def resource_state(self, resource: str) -> States:
        return list(self.held_resources.get(resource, {}).items())

    def lock_resource(self, transaction: int, resource: str, lock_type: States):
        self.held_locks.setdefault(transaction, {})[
            resource] = lock_type
        self.held_resources.setdefault(
            resource, {})[transaction] = lock_type
        return [Command("granted", transaction, resource, lock_type)]

    def wait_for_lock(self, transaction: int, resource: str, old_lock_type: States, next_lock_type: States):
        old_transaction = self.resource_state(resource)[0][0]
        self.resource_fifo.setdefault(resource, {})[
            transaction] = next_lock_type

        return [Command("waiting",
                        transaction, resource, next_lock_type,
                        extra={'lock_type': old_lock_type, 'transaction': old_transaction})]

    def wait_for_lock_upgrade(self, transaction: int, resource: str, old_lock_type: States, next_lock_type: States):
        old_transaction = self.resource_state(resource)[1][0]
        self.resource_fifo.setdefault(resource, {})[transaction] = States.xlock

        return [Command("waiting_upgrade",
                        transaction, resource, next_lock_type,
                        extra={'lock_type': old_lock_type, 'transaction': old_transaction})]

    def unlock(self, transaction: int, resource: str, lock_type: States):
        del self.held_locks[transaction][resource]
        del self.held_resources[resource][transaction]

        return [Command('unlocked', transaction, resource, lock_type)]

    def grant_next_locks(self, resource: str):
        cmds = []

        # Grant all locks waiting, there are two cases:
        # 1. the following locks are slock (until a xlock is found or end of waiting locks are reached),
        # in this case, all these slocks will be granted.
        # 2. there are a xlock, in this case only this will be granted.
        while len(self.resource_fifo.get(resource, {})) > 0:
            transaction, lock_type = list(
                self.resource_fifo[resource].items())[0]

            # upgrade case
            if self.held_resources.get(resource).get(transaction) is States.slock:
                cmds.append(
                    Command("upgrade_to", transaction))
            else:  # normal case
                cmds.append(
                    Command("granted_to", transaction, resource, lock_type))

            self.held_resources.setdefault(resource, {})[
                transaction] = lock_type
            del self.resource_fifo[resource][transaction]
            self.held_locks.setdefault(transaction, {})[
                resource] = lock_type

            # if the previous granted lock was xlock, no need to grant more
            if lock_type is States.xlock:
                break
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

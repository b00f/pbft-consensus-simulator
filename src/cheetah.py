import time
from .message import Message
from .network import Network
from .node import Node

d_NULL = 0


class CheetahNode(Node):
    def __init__(self, node_id: int, N: int, f: int, disable_logs: bool):
        self.node_id = node_id
        self.committed = {}
        self.N = N
        self.f = f
        self.decided_value = None
        self.phase = "IDLE"
        self.view = 0
        self.cp_round = 0
        self.cp_pre_votes = []
        self.cp_main_votes = []
        self.primary = 0
        self.disable_logs = disable_logs

    def get_node_id(self) -> int:
        return self.node_id

    def set_network(self, network: Network):
        self.network = network

    def is_decided(self):
        return self.phase == "DECIDED"

    def handle_message(self, msg: Message):
        if msg.view != self.view:
            return

        match msg.msg_type:
            case "<<REQUEST>>":
                self.handle_request(msg)
            case "<<PRE-PREPARE>>":
                self.handle_pre_prepare(msg)
            case "<<COMMIT>>":
                self.handle_commit(msg)
            case "<<REPLY>>":
                self.handle_reply(msg)
            case "<<CP:PRE-VOTE>>":
                self.handle_cp_pre_vote(msg)
            case "<<CP:MAIN-VOTE>>":
                self.handle_cp_main_vote(msg)
            case "<<CP:DECIDE>>":
                self.handle_cp_decide(msg)

    def send_message(self, msg: Message):
        self.debug(f"sent message {msg}")
        self.network.broadcast(msg)
        self.handle_message(msg)

    def handle_request(self, msg: Message):
        if self.phase == "IDLE":
            self.phase = "PRE-PREPARE"
            self.debug(f"moved to PRE-PREPARE phase")

            if self.node_id == self.primary:
                pre_prepare_msg = Message(
                    self.node_id,
                    msg.value,  ## The client request message
                    self.view,
                    "<<PRE-PREPARE>>",
                )
                self.send_message(pre_prepare_msg)

    def handle_pre_prepare(self, msg: Message):
        if self.phase == "PRE-PREPARE":
            self.phase = "COMMIT"
            self.debug(f"moved to COMMIT phase")

            commit_msg = Message(self.node_id, msg.value, self.view, "<<COMMIT>>")
            self.send_message(commit_msg)

    def handle_commit(self, msg: Message):
        if self.phase == "COMMIT":
            self.committed[msg.sender] = msg
            if len(self.committed) >= (3 * self.f) + 1:
                self.phase = "DECIDED"
                self.decided_value = msg.value
                self.debug(f"DECIDED on value: {self.decided_value}")

                reply_msg = Message(self.node_id, msg.value, self.view, "<<REPLY>>")
                self.send_message(reply_msg)

    def handle_reply(self, msg: Message):
        # Reply messages are considered as checkpointing messages.
        # Any replica can make a decision upon receiving a valid Reply message,
        # even if the local log does not have enough votes.
        self.phase = "DECIDED"
        self.decided_value = msg.value

    def timer_expired(self):
        self.send_cp_pre_vote()

    def send_cp_pre_vote(self):
        self.phase = "CP:PRE-VOTE"
        self.debug(f"moved to CP:PRE-VOTE phase")
        self.cp_pre_votes.append({})
        self.cp_main_votes.append({})

        if self.cp_round == 0:
            cp_value = "Yes"
            if len(self.committed) >= (2 * self.f) + 1:
                cp_value = "No"
        else:
            rnd_main_vote = next(iter(self.cp_main_votes[self.cp_round - 1].values()))
            if rnd_main_vote.data == "Yes":
                cp_value = "Yes"
            elif rnd_main_vote.data == "No":
                cp_value = "No"
            else:  # All are Abstain
                cp_value = "No"  # Biased value

        cp_data = (self.cp_round, cp_value)
        cp_pre_vote_msg = Message(
            self.node_id, None, self.view, "<<CP:PRE-VOTE>>", cp_data
        )
        self.send_message(cp_pre_vote_msg)

        self.debug(f"requested view change to view {self.view + 1}")

    def handle_cp_pre_vote(self, msg: Message):
        if self.phase == "CP:PRE-VOTE":
            if msg.data[0] != self.cp_round:
                return

            pre_votes = self.cp_pre_votes[self.cp_round]
            pre_votes[msg.sender] = msg

            if len(pre_votes) >= (2 * self.f) + 1:
                no_count = sum(1 for msg in pre_votes.values() if msg.data[1] == "No")
                yes_count = sum(1 for msg in pre_votes.values() if msg.data[1] == "Yes")

                # Optimization for biased ABBA
                # If a replica collects 2f +1 Pre-Votes for value 0 in any round, it can decide on value 0
                if no_count >= (2 * self.f) + 1:
                    reply_msg = Message(self.node_id, msg.value, self.view, "<<REPLY>>")
                    self.send_message(reply_msg)
                    return

                self.phase = "CP:MAIN-VOTE"
                self.debug(f"moved to CP:MAIN-VOTE phase")

                cp_value = "Abstain"
                if yes_count >= (2 * self.f) + 1:
                    cp_value = "Yes"

                cp_data = (self.cp_round, cp_value)
                cp_pre_vote_msg = Message(
                    self.node_id, None, self.view, "<<CP:MAIN-VOTE>>", cp_data
                )
                self.send_message(cp_pre_vote_msg)

    def handle_cp_main_vote(self, msg: Message):
        if self.phase == "CP:MAIN-VOTE":
            if msg.data[0] != self.cp_round:
                return

            main_votes = self.cp_main_votes[self.cp_round]
            main_votes[msg.sender] = msg
            if len(main_votes) >= (2 * self.f) + 1:
                yes_count = sum(
                    1 for msg in main_votes.values() if msg.data[1] == "Yes"
                )

                if yes_count >= (2 * self.f) + 1:
                    self.phase = "COMMIT"
                    self.cp_round = 0
                    self.cp_pre_votes = []
                    self.cp_main_votes = []
                    self.view += 1
                    self.debug(f"moved to COMMIT phase")

                    commit_msg = Message(self.node_id, d_NULL, self.view, "<<COMMIT>>")
                    self.send_message(commit_msg)

                else:
                    self.phase = "CP:PRE-VOTE"
                    self.cp_round += 1
                    self.debug(f"moved to CP:PRE-VOTE phase")

    def debug(self, log: str):
        if not self.disable_logs:
            print(f"Node {self.node_id}, View {self.view}: {log}")

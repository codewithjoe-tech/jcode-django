"""
Django edge plugin for jcode.

Detects three patterns in Python files:

1. URL routing — path('url/', view_fn) / re_path(...) / url(...)
   → ROUTE edge: caller module → view function
   Useful for blast-radius: change a view → find the URLs that expose it.

2. Model relations — ForeignKey(Model) / OneToOneField / ManyToManyField
   → REFERENCES edge: caller class → referenced model
   Useful for blast-radius: change a model → find every model that FK-links to it.

3. Signal receivers — @receiver(post_save, sender=Model) decorator
   → SIGNAL edge: decorated function → sender model
   Useful for blast-radius: change a model → find all signal handlers triggered by it.
"""
from jcode.domain.models import Edge, Node, NodeId, NodeType
from jcode.storage.object_store import node_id_for

EDGE_ROUTE      = "route"
EDGE_REFERENCES = "references"
EDGE_SIGNAL     = "signal"

_URL_NAMES      = frozenset({"path", "re_path", "url"})
_RELATION_NAMES = frozenset({"ForeignKey", "OneToOneField", "ManyToManyField", "ForeignObject"})
_SIGNAL_NAMES   = frozenset({"receiver"})


def _text(ts_node, source: bytes) -> str:
    return source[ts_node.start_byte:ts_node.end_byte].decode("utf-8", errors="replace")


def _provisional(name: str, node_type: NodeType = NodeType.FUNCTION) -> Node:
    ph = Node(
        id=NodeId("0" * 64), node_type=node_type,
        name=name, title=name, file_path="<unresolved>",
        line_start=0, line_end=0,
    )
    return Node(
        id=node_id_for(ph), node_type=node_type,
        name=name, title=name, file_path="<unresolved>",
        line_start=0, line_end=0,
    )


def _positional_args(arg_list) -> list:
    return [
        c for c in arg_list.children
        if c.type not in (",", "(", ")", "comment") and c.type != "keyword_argument"
    ]


def _resolve_view_arg(node, source: bytes) -> str | None:
    if node.type == "identifier":
        name = _text(node, source)
        return None if name == "include" else name
    if node.type == "attribute":
        for child in reversed(node.children):
            if child.type == "identifier":
                return _text(child, source)
    if node.type == "call":
        fn = node.children[0] if node.children else None
        if fn and fn.type == "attribute":
            for child in fn.children:
                if child.type == "identifier":
                    name = _text(child, source)
                    if name not in ("as_view", "as_view()"):
                        return name
        if fn and fn.type == "identifier":
            name = _text(fn, source)
            if name != "include":
                return name
    return None


def _resolve_model_arg(node, source: bytes) -> str | None:
    if node.type == "identifier":
        return _text(node, source)
    if node.type in ("string", "concatenated_string"):
        raw = _text(node, source).strip("\"'")
        return raw.split(".")[-1] if raw else None
    return None


class DjangoPlugin:
    """Implements the jcode EdgePlugin protocol for Django."""

    @property
    def handled_names(self) -> frozenset:
        return _URL_NAMES | _RELATION_NAMES | _SIGNAL_NAMES

    def handle_call(self, call_node, source: bytes, caller: Node):
        fn_node = call_node.children[0] if call_node.children else None
        if fn_node is None:
            return [], []
        callee = _text(fn_node, source).split(".")[-1]
        arg_list = next((c for c in call_node.children if c.type == "argument_list"), None)
        if arg_list is None:
            return [], []
        if callee in _URL_NAMES:
            return self._handle_url(arg_list, source, caller)
        if callee in _RELATION_NAMES:
            return self._handle_relation(arg_list, source, caller)
        if callee in _SIGNAL_NAMES:
            return self._handle_receiver(arg_list, source, caller)
        return [], []

    def _handle_url(self, arg_list, source: bytes, caller: Node):
        pos = _positional_args(arg_list)
        if len(pos) < 2:
            return [], []
        view_name = _resolve_view_arg(pos[1], source)
        if not view_name:
            return [], []
        prov = _provisional(view_name, NodeType.FUNCTION)
        return [prov], [Edge(source_id=caller.id, target_id=prov.id, edge_type=EDGE_ROUTE)]

    def _handle_relation(self, arg_list, source: bytes, caller: Node):
        pos = _positional_args(arg_list)
        if not pos:
            return [], []
        model_name = _resolve_model_arg(pos[0], source)
        if not model_name or model_name == "self":
            return [], []
        prov = _provisional(model_name, NodeType.CLASS)
        return [prov], [Edge(source_id=caller.id, target_id=prov.id, edge_type=EDGE_REFERENCES)]

    def _handle_receiver(self, arg_list, source: bytes, caller: Node):
        sender_node = None
        for child in arg_list.children:
            if child.type != "keyword_argument":
                continue
            kw_children = list(child.children)
            if (
                len(kw_children) >= 3
                and kw_children[0].type == "identifier"
                and _text(kw_children[0], source) == "sender"
            ):
                sender_node = kw_children[2]
                break
        if sender_node is None:
            return [], []
        model_name = _resolve_model_arg(sender_node, source)
        if not model_name:
            return [], []
        prov = _provisional(model_name, NodeType.CLASS)
        return [prov], [Edge(source_id=caller.id, target_id=prov.id, edge_type=EDGE_SIGNAL)]


def create() -> DjangoPlugin:
    return DjangoPlugin()

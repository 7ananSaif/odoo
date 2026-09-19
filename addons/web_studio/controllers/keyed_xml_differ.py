import re
from bisect import bisect_left
from copy import deepcopy
from itertools import chain
from collections.abc import Iterable
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Callable, Union, Literal, TypeAlias
from lxml import etree

Element = etree.Element


## SOME XML UTILS
INDENT_RE = re.compile(r"(^\n[\s\t]*)|(\n[\s\t]*$)")


def append_text(node, text):
    if len(node) > 0:
        tail = (node[-1].tail or "") + (text or "")
        node[-1].tail = tail or None
    else:
        text = (node.text or "") + (text or "")
        node.text = text or None


def dedent_tree(elem):
    for el in elem.iter(tag=(etree.Element, etree.Comment)):
        if el.text is not None and not isinstance(el, etree._Comment):
            el.text = INDENT_RE.sub("", el.text) or None
        if el.tail is not None:
            el.tail = INDENT_RE.sub("", el.tail) or None


def indent_tree(elem, level=1, spaces=2):
    """
    The lxml library doesn't pretty_print xml tails, this method aims
    to solve this.

    Returns the elem with properly indented text and tail
    """
    # See: http://lxml.de/FAQ.html#why-doesn-t-the-pretty-print-option-reformat-my-xml-output
    # Below code is inspired by http://effbot.org/zone/element-lib.htm#prettyprint
    indent_texts = elem.tag == "xpath"

    len_elem = len(elem)
    if len_elem:
        i = "\n" + level * spaces * " "
        prev_i = "\n" + (level - 1) * spaces * " "

        if indent_texts or (not elem.text or not elem.text.strip()):
            text = elem.text
            elem.text = (text.strip() + i) if text else i
        index = 0
        while (index < len_elem):
            subelem = elem[index]
            tail = (subelem.tail or "").strip()
            if indent_texts or not tail:
                if index == len_elem - 1:
                    subelem.tail = (i + tail + prev_i) if tail else prev_i
                else:
                    subelem.tail = (i + tail + i) if tail else i
            indent_tree(subelem, level + 1, spaces)
            index += 1
    return elem


def visit(node, do_children=lambda n: True):
    yield node
    if do_children(node) is False:
        return
    for child in node.iterchildren(etree.Element):
        yield from visit(child, do_children)


def _visit_new_node(new_node):
    yield from visit(new_node, lambda n: not n.get(DIFF_ATTRIBUTE))


## TOOLS TO MAKE THE DIFF
def diff_dicts(old: etree._Attrib, new: etree._Attrib, ignored_keys: Optional[set] = frozenset()) -> dict:
    return {
        k: new.get(k) for k in sorted(set().union(old, new))
        if k not in ignored_keys and old.get(k) != new.get(k)
    }


def longest_increasing_subsequence(arr):
    """Returns the longest increasing subsequence of a list of unordered values
    Largely inspired from https://en.wikipedia.org/wiki/Longest_increasing_subsequence
    and by https://cp-algorithms.com/sequences/longest_increasing_subsequence.html

    It compares items on their value: in the case items are string: "11" < "2" == True.
    So, transforming an item to its value if necessary should be done before hand

    As it returns the biggest list of stable elements in the list,
    it is useful to compute the least amount of moving items into that list

    eg: [3,1,2] : 1 and 2 did not move, 3 is just placed before 1
    longest_increasing_subsequence = [2,1] (the output is the reversed of the subsequence)
    """
    if not arr:
        return []

    previous = {}
    first, *list_arr = arr
    smallest_endings = [first]
    for el in list_arr:
        if el < smallest_endings[-1]:
            target_index = bisect_left(smallest_endings, el)
            previous[el] = smallest_endings[target_index - 1]
            smallest_endings[target_index] = el
        else:
            previous[el] = smallest_endings[-1]
            smallest_endings.append(el)

    sequence = []
    el = smallest_endings[-1]
    for _el in smallest_endings:
        sequence.append(el)
        el = previous.get(el)

    return sequence


Position = Literal["replace", "attributes", "move", "before", "after", "inside"]

# Leaves are representation of the elements in the Tree
# to ease their management


@dataclass
class TextLeaf:
    element: Optional[str] = None
    ignores: set[Position] = field(default_factory=set)

    def __post_init__(self):
        self.element = INDENT_RE.sub("", self.element or "") or None


@dataclass
class NodeLeaf:
    element: etree._Element = None
    id: Optional[str] = None
    is_owned: bool = False


@dataclass
class CommentLeaf:
    element: Optional[str] = None


Leaf: TypeAlias = Union[TextLeaf, NodeLeaf, CommentLeaf]

XMLInput: TypeAlias = Union[etree._ElementTree, etree._Element, str]


def _group_by_pivot(iterable: Iterable, is_pivot: Callable):
    """Group the iterable's elements according to an unmoving pivor (or target). Similar to
    itertools.groupy, except it needed to be "read ahead" as the target of a leaf
    can be before any pivot node.
    returns a Generator, of which iterations are composed by a tuple (target, position), elements
        if target and position are None, no pivot has been found.
        if position is None, the pivot is the last one.

    :param: iterable
    :param: is_pivot

    :return: Generator: Tuple: (target, position), list[elements].
    """
    current_pivot = None
    current_group = []
    left_overs = []
    for elem in iterable:
        new_pivot = is_pivot(elem)
        if new_pivot in (None, False):
            if current_pivot in (None, False):
                left_overs.append(elem)
            else:
                current_group.append(elem)
        elif current_pivot not in (None, False):
            if current_group:
                yield (current_pivot, "after"), current_group
                current_group = []
            current_pivot = new_pivot
        else:
            if left_overs:
                yield (new_pivot, "before"), left_overs
                left_overs = []
            current_pivot = new_pivot
    if left_overs or current_group:
        yield (current_pivot, None), left_overs or current_group


def _get_subtree_and_ancestors(node: etree._Element, is_subtree=lambda n: False) -> tuple[etree._Element | None, list[etree._Element]]:
    """For a node, returns its subtree parent (a relevant parent node that indicates a tree that could be separate)
    eg:
    <form> (this is a subtree)
        <div>
            <field>
                <list> (this is a subtree)

    and its ancestors (excluding the subtree) in opposite order from the document's (ie bottom-up)
    """
    ancestors = []
    for ancestor in node.iterancestors(etree.Element):
        if is_subtree(ancestor):
            return ancestor, ancestors
        ancestors.append(ancestor)
    return None, ancestors


def _standardize_target_position(target, position, parent):
    """The _group_by_pivot function returns an abstract target/position tuple
    This function converts that into the behavior we want.
    """
    if target is not None and position is None:
        return target, "after"
    else:
        return target if target is not None else parent, position or "inside"


def is_node_empty(node):
    return len(node) == 0 and node.text is None


def _texts_concat(texts, null_value=None):
    return "".join(t or "" for t in texts) or null_value


def _leaves_repr(leaves: list[Leaf]):
    texts = []
    for leaf in leaves:
        match leaf:
            case NodeLeaf(id=id):
                if texts:
                    yield (None, _texts_concat(texts))
                    texts = []
                yield (id or "new", None)
            case TextLeaf(element=element):
                if element:
                    texts.append(element)
    if texts:
        yield (None, _texts_concat(texts))


def append_leaf(leaves, leaf: Leaf):
    if isinstance(leaf, TextLeaf):
        prev = leaves[-1] if len(leaves) > 0 else None
        if isinstance(prev, TextLeaf):
            prev.element = _texts_concat(lf.element for lf in [prev, leaf])
            return
    leaves.append(leaf)


DIFF_ATTRIBUTE = "o-diff-key"


class DiffAnalyzer:
    """Class that parses both trees and determines what has changed between the two.
    For each pair, it computes the differences in the attributes and in content.
    Changes are understood as a mapping from node_id to the things (added, removed, moving nodes)
    at that spot precisely.
    It uses a NodeTracker to globally register what happens in terms of nodes moving around.
    The two sets of data are necessary to ensure we do things with a global perspective, but also
    be able to put the relevant changes around a node grouped together.
    """
    def __init__(
        self,
        ignore_attributes=None,
        on_new_node=lambda n: True,
        is_subtree=lambda n: False,
        get_moving_candidate_key=lambda n: None,
    ):
        self.ignore_attributes = set(
            [] if ignore_attributes is None else ignore_attributes
        )
        self.on_new_node = on_new_node
        self.is_subtree = is_subtree

        self.changes = {}
        self.tracker = NodeTracker(get_moving_candidate_key)

    def diff(self, old: XMLInput, new: XMLInput) -> dict:
        old_tree = self._build_tree_from_input(old)
        new_tree = self._build_tree_from_input(new)

        self.map_id_to_node_old = {node.get(DIFF_ATTRIBUTE): node for node in old_tree.iter(etree.Element)}
        self.tracker.keep(new_tree.get(DIFF_ATTRIBUTE))
        self._diff_nodes(self.map_id_to_node_old[new_tree.get(DIFF_ATTRIBUTE)], new_tree)

        return {
            "changes": self.changes,
            "original_node_map": self.map_id_to_node_old,
            "node_tracker": self.tracker,
        }

    def _build_tree_from_input(self, diff_input: XMLInput) -> etree._ElementTree:
        if isinstance(diff_input, (etree._ElementTree, etree._Element)):
            return deepcopy(diff_input)
        else:
            parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)
            return etree.fromstring(diff_input, parser=parser)

    def _diff_nodes(self, old, new):
        old_set_node_ids = set()

        old_leaves: list[Leaf] = [TextLeaf(old.text)]
        comments = set()

        for child in old.iterchildren(tag=(etree.Element, etree.Comment)):
            if isinstance(child, etree._Comment):
                comments.add(repr(child))
                append_leaf(old_leaves, TextLeaf(child.tail))
                continue
            nid = child.get(DIFF_ATTRIBUTE)
            old_set_node_ids.add(nid)
            old_leaves.extend([
                NodeLeaf(element=child, id=nid),
                TextLeaf(element=child.tail),
            ])

        leaves = []  # represents children and texts. They will be grouped according to their nearest unmoving sibling
        kept_nodes = []  # nodes' id that are still present
        children_to_diff = {}  # a map id to new node to continue the iteration of the tree
        removed_nodes = set(old_set_node_ids)  # children of the main node that will be removed
        candidates_move = []  # gather new nodes that potentially have a removed counterpart

        leaves.append(TextLeaf(new.text))
        for child in new.iterchildren(tag=(etree.Element, etree.Comment)):
            if isinstance(child, etree._Comment):
                if repr(child) not in comments:
                    leaves.append(CommentLeaf(child))
                append_leaf(leaves, TextLeaf(child.tail))
                child.tail = None
                continue
            nid = child.get(DIFF_ATTRIBUTE)
            is_owned = nid in old_set_node_ids
            candidate_key = None

            if nid:
                children_to_diff[nid] = child
                if is_owned:
                    self.tracker.keep(nid)
                    kept_nodes.append(int(nid))
                    removed_nodes.remove(nid)
                else:
                    self.tracker.move(nid)
            else:
                candidate_key = self.tracker.moving_candidate(child)
                if candidate_key is not None:
                    kept_nodes.append(candidate_key)
                    candidates_move.append((candidate_key, False))
                else:
                    for new_child in _visit_new_node(child):
                        if _nid := new_child.get(DIFF_ATTRIBUTE):
                            self.tracker.move(_nid)
                            children_to_diff[_nid] = new_child
                        elif candidate_key := self.tracker.moving_candidate(new_child):
                            candidates_move.append((candidate_key, True))
            leaves.extend([
                NodeLeaf(element=child, id=nid, is_owned=is_owned),
                TextLeaf(element=child.tail),
            ])

        attributes_changes = diff_dicts(old.attrib, new.attrib, self.ignore_attributes)
        has_body_changes = tuple(_leaves_repr(old_leaves)) != tuple(_leaves_repr(leaves))
        if not has_body_changes and not attributes_changes:
            for nid, new_child in children_to_diff.items():
                self._diff_nodes(self.map_id_to_node_old[nid], new_child)
            return

        command = {"attributes": attributes_changes, "new_node": new, "new_leaves": leaves}
        if has_body_changes:
            command.update(
                candidates_move=candidates_move,
                kept_nodes=kept_nodes,
                removed_nodes=removed_nodes,
                old_leaves=old_leaves,
            )
        self.changes[old.get(DIFF_ATTRIBUTE)] = command

        for nid, new_child in children_to_diff.items():
            self._diff_nodes(self.map_id_to_node_old[nid], new_child)

    def _get_moving_candidate_key(self, node):
        """From a node, determines whether it is electable to be a moving
        node. Valid candidates should:
        - be empty (no children, no text)
        - have a not None key
        - be in a subtree that was here in the old tree (has a DIFF ID)"""
        if len(node) > 0 or (node.text or "").strip():
            return
        key = self.__get_moving_candidate_key(node)
        if key is None:
            return
        subtree, _ = _get_subtree_and_ancestors(node, self.is_subtree)
        if subtree is None or not subtree.get(DIFF_ATTRIBUTE):
            return
        return tuple(chain([subtree.get(DIFF_ATTRIBUTE)], key))


class KeyedXmlDiffer:
    """A class that allows to compute the difference between two trees, of which we know one is a modification of the other.
    Namely, both trees have nodes that have a unique ID, each node in the new tree is compared to its
    counterpart in the old one.
    Hence the recommended flow:
    - assign ids on the original tree
    - ids must be convertible to int, and increasing with the tree's order (depth first)
    - do some operation on that modified tree
    - compare the original tree with the modified one

    It supports moving, removing nodes, altering texts, altering the order of a node's children, modifying attributes of a node
    It doesn't support changing the tag name of a node
    It doesn't support anything else than Elements, in particular, comments and their tail will be ignored

    The `diff` method returns an abstraction describing what happened for a node with a given id
    The `diff_xpath` method computes the Odoo's xpath notation to be used as an inherited view

    The expected complexity is O(n log n), because of the use of bisect.
    It could be higher when we compute the xpath for each touched nodes.
    We still have to browse several times the trees.
    """

    @classmethod
    def assign_node_ids_for_diff(cls, tree):
        for index, desc in enumerate(tree.iter(etree.Element)):
            desc.set(DIFF_ATTRIBUTE, str(index))

    def __init__(
        self,
        ignore_attributes=None,
        on_new_node=lambda n: True,
        is_subtree=lambda n: False,
        xpath_with_meta=False,
        get_moving_candidate_key=lambda n: None,
    ):
        # User-defined parameters
        self.ignore_attributes = set([] if ignore_attributes is None else ignore_attributes)
        self.on_new_node = on_new_node
        self.attributes_identifiers = {
            "id": True,
            "name": True,
            "for": True,
            "t-name": True,
            "t-call": True,
            "t-field": True,
            "t-set": True,
        }
        self.is_subtree = is_subtree
        self.xpath_with_meta = xpath_with_meta

        # Internal State
        self.new_id = 1

        self.analyzer = DiffAnalyzer(
            ignore_attributes=ignore_attributes,
            on_new_node=on_new_node,
            is_subtree=is_subtree,
            get_moving_candidate_key=get_moving_candidate_key,
        )

    # Basic diffing abstraction
    def diff(self, old: XMLInput, new: XMLInput):
        return self.analyzer.diff(old, new)

    # Methods that concern the building of the Odoo's xpath semantic tree
    def diff_xpath(self, old: XMLInput, new: XMLInput, flat: bool = False) -> str:
        diff = self.diff(old, new)
        changes = diff["changes"]

        self.tracker = diff["node_tracker"]
        self.map_id_to_node_old = diff["original_node_map"]
        self.new_nodes_map: dict[str, etree._Element] = {}

        return self._build_xpath_operations(changes, flat)

    def _build_xpath_operations(self, changes: dict, flat: bool) -> str:
        # gather nodes that are moving around
        for change in changes.values():
            for rm_id in change.get("removed_nodes", []):
                if self.tracker.is_removed(rm_id):
                    el = self.map_id_to_node_old[rm_id]
                    candidate = self.tracker.moving_reference(el)
                    if candidate is not None:
                        self.tracker.keep(rm_id)
                        candidate.set(DIFF_ATTRIBUTE, el.get(DIFF_ATTRIBUTE))

        traversed = set()
        for nid in self.tracker.move_ids:
            node = self.map_id_to_node_old[nid]
            for ancestor in node.iterancestors(etree.Element):
                ancestor_id = ancestor.get(DIFF_ATTRIBUTE)
                if ancestor_id in traversed:
                    break
                else:
                    traversed.add(ancestor_id)
                if self.tracker.is_removed(ancestor_id):
                    self.tracker.delay_remove(ancestor_id)
                    break

        # Gather virtual xpaths operations
        xpath_operations_bundles = []

        for main_id, change in changes.items():
            if self.tracker.is_removed(main_id):
                continue

            main_xpaths_list = deque()
            sub_xpath_list = []
            replace_targets = set()

            ## O. Heart of the system: inside a node, determines unmoving children
            ## Determine what operations to do around those pivots (replace/after/before/inside)
            ## Determine whether we *can* do those operation given the surrounding texts.
            if "kept_nodes" in change:
                kept_nodes_ids = []
                for key in change["kept_nodes"]:
                    if isinstance(key, int):
                        kept_nodes_ids.append(key)
                    else:
                        ref, _ = self.tracker.get_from_key(key)
                        if ref is not None:
                            kept_nodes_ids.append(int(ref.get(DIFF_ATTRIBUTE)))

                pivot_nodes = {str(k) for k in longest_increasing_subsequence(kept_nodes_ids)}
                should_full_replace = False

                def is_pivot(leaf):
                    return nid if (nid := isinstance(leaf, NodeLeaf) and leaf.element.get(DIFF_ATTRIBUTE)) in pivot_nodes else None

                old_leaves = change["old_leaves"]
                new_leaves = change["new_leaves"]
                old_pivoting = {_standardize_target_position(target, position, main_id): leaves for (target, position), leaves in _group_by_pivot(old_leaves, is_pivot)}

                for (target, position), new_leaves in _group_by_pivot(new_leaves, is_pivot):
                    target, position = _standardize_target_position(target, position, main_id)

                    replace_target, old_leaves_with_removals = self._parse_old_leaves(old_pivoting.get((target, position), []))
                    if replace_target:
                        texts_compatible = self._leaves_text_compatibility(old_leaves_with_removals, new_leaves, "replace")
                        if not texts_compatible:
                            replace_target = None
                        else:
                            position = "replace"
                            target = replace_target
                            replace_targets.add(target)
                    if position != "replace":
                        texts_compatible = self._leaves_text_compatibility(old_leaves_with_removals, new_leaves, position)
                        if not texts_compatible:
                            should_full_replace = True
                            break

                    xpath_operation = Element("xpath", expr=target, position=position)
                    main_xpaths_list.append(xpath_operation)

                    self.fill_xpath_node(new_leaves, xpath_operation, sub_xpath_list, position)

                if should_full_replace:
                    main_xpaths_list, sub_xpath_list = self._handle_node_full_replace(main_id, change)
                    xpath_operations_bundles.append([main_xpaths_list, sub_xpath_list])
                    continue

            ## 1. Remove nodes first, that way browsing that subtree will be easier
            for cnid in change.get("removed_nodes", []):
                if self.tracker.is_removed(cnid, include_delayed=False) and cnid not in replace_targets:
                    main_xpaths_list.appendleft(Element("xpath", expr=cnid, position="replace"))

            ## 2. Make the changes onto the attributes. It is last because the node's identifiers
            ## and consequently the node's xpath may be affected
            main_xpaths_list.extend(self._build_xpaths_attributes(change["attributes"], main_id))
            xpath_operations_bundles.append([main_xpaths_list, sub_xpath_list])

            ## 3. Build xpath for new nodes which have a fully removed counterpart
            ## that is close enough (same key) to be reconciled with it.
            for candidate_key, in_new_node in change.get("candidates_move", []):
                ref, candid = self.tracker.get_from_key(candidate_key)
                if ref is not None:
                    xpath_ops = self._build_xpaths_attributes(diff_dicts(ref.attrib, candid.attrib, self.ignore_attributes), ref.get(DIFF_ATTRIBUTE))
                    if in_new_node:
                        sub_xpath_list.extend(xpath_ops)
                    else:
                        main_xpaths_list.extend(xpath_ops)

        ## Remove nodes for which at least one children was moved around and still present
        if self.tracker.delayed_remove:
            delayed_xpaths = []
            xpath_operations_bundles.append([delayed_xpaths])
            for rm_id in self.tracker.delayed_remove:
                xpath_element = Element("xpath", expr=rm_id, position="replace")
                delayed_xpaths.append(xpath_element)

        ## Build the actual xpath tree
        diff_as_arch = Element("data")
        for operation_bundle in xpath_operations_bundles:
            bundle_sub_element = Element("data") if not flat else diff_as_arch
            for operation_list in operation_bundle:
                for xpath_node in operation_list:
                    self._apply_xpath_operation(xpath_node)
                    if xpath_node.get("position") != "replace" and is_node_empty(xpath_node):
                        continue
                    bundle_sub_element.append(xpath_node)
            if not is_node_empty(bundle_sub_element) and bundle_sub_element != diff_as_arch:
                diff_as_arch.append(bundle_sub_element)

        ## Clean up the result from some metadata
        for node in diff_as_arch.iter(etree.Element):
            node.attrib.pop("o-diff-new-id", None)

        if len(diff_as_arch) == 0:
            return ""
        indent_tree(diff_as_arch)
        return etree.tostring(diff_as_arch, encoding="unicode")

    def _build_xpaths_attributes(self, attributes_changes, expr_id):
        if attributes_changes:
            xpath_attrs = Element("xpath", expr=expr_id, position="attributes")
            for key, value in attributes_changes.items():
                attr_node = etree.Element("attribute", name=key)
                attr_node.text = value
                xpath_attrs.append(attr_node)
            return [xpath_attrs]
        return []

    def fill_xpath_node(
        self,
        leaves: list[Leaf],
        target_xpath: etree._Element,
        sub_xpath_list,
        ignored_position: Optional[Position] = None,
    ):
        for leaf in leaves:
            match leaf:
                case TextLeaf(element=element):
                    if not ignored_position or ignored_position not in leaf.ignores:
                        append_text(target_xpath, element)
                case CommentLeaf(element=element):
                    target_xpath.append(element)
                case NodeLeaf(element=element):
                    if diff_id := element.get(DIFF_ATTRIBUTE):
                        target_xpath.append(Element("xpath", expr=diff_id, position="move"))
                    else:
                        new_element, sub_operations = self._handle_new_node(element)
                        target_xpath.append(deepcopy(new_element))
                        sub_xpath_list.extend(sub_operations)

    def _apply_xpath_operation(self, xpath_node):
        """Apply the relevant changes of xpath_node onto the old tree.
        We are incrementally changing the old tree to be able to locate each node and
        accurately compute their xpath as they move around.
        This function reproduces partially what is done in template_inheritance.
        Except that here we don't care about tails or texts or attributes, as only the relative
        position of nodes is crucial for us.
        """
        expr, position, new_target = [xpath_node.get(attr) for attr in ["expr", "position", "new_target"]]
        if not new_target:
            target_node = self.map_id_to_node_old[expr]
        else:
            target_node = self.new_nodes_map[expr]

        xpath_node.set("expr", self._get_xpath(target_node))

        if position == "move":
            self._redo_xpath_node(xpath_node, target_node)
            return target_node

        last_target = target_node
        for content in xpath_node:
            if new_id := content.get("o-diff-new-id"):
                content = self.new_nodes_map[new_id]
            elif content.tag == "xpath":
                content = self._apply_xpath_operation(content)
            else:
                content = deepcopy(content)

            if position == "before":
                target_node.addprevious(content)
            elif position in ("after", "replace"):
                last_target.addnext(content)
                last_target = content
            elif position == "inside":
                target_node.append(content)

        self._redo_xpath_node(xpath_node, target_node)
        if position == "replace":
            target_node.getparent().remove(target_node)

    def _handle_new_node(self, new_node):
        """When a node was not present in the old tree (it doesn't have an DIFF-ID)
        we should browse it recursively to detect old nodes that have been moved inside.
        We build xpaths to place those move correctly.
        The new node may be altered when a old node has been moved inside, surrounded by texts.
        """
        new_node = deepcopy(new_node)
        new_node.tail = None
        parents = {}
        for node in _visit_new_node(new_node):
            nid = node.get(DIFF_ATTRIBUTE)
            if nid:
                parents[node.getparent()] = True
                node.clear(keep_tail=True)
                node.set(DIFF_ATTRIBUTE, nid)
            else:
                node.set("o-diff-new-id", str(self.new_id))
                self.new_nodes_map[str(self.new_id)] = node
                self.new_id += 1
                self.on_new_node(node)

        def is_pivot(n):
            return None if n.get(DIFF_ATTRIBUTE) else n

        xpath_list = []
        for parent in parents:
            for (target, position), children in _group_by_pivot(parent.iterchildren(etree.Element), is_pivot):
                target, position = _standardize_target_position(target, position, parent)
                xpath_element = Element("xpath", expr=target.get("o-diff-new-id"), position=position, new_target="1")
                xpath_list.append(xpath_element)
                if position == "after":
                    tail = INDENT_RE.sub("", target.tail or "") or None
                    target.tail = INDENT_RE.sub("", children[-1].tail or "") or None
                    children[-1].tail = None
                    xpath_element.text = tail

                after_text = None
                if position == "before":
                    if (prev := target.getprevious()) is not None:
                        after_text = prev.tail
                        prev.tail = None
                    else:
                        parent = target.getparent()
                        after_text = parent.text
                        parent.text = None
                    after_text = INDENT_RE.sub("", after_text or "") or None

                parent = children[0].getparent() if len(children) else None
                for child in children:
                    xpath_element.append(Element("xpath", expr=child.get(DIFF_ATTRIBUTE), position="move"))
                    append_text(xpath_element, INDENT_RE.sub("", child.tail or "") or None)
                    parent.remove(child)
                append_text(xpath_element, after_text)

        return new_node, xpath_list

    def _get_identifiers(self, node):
        node_attrib = node.attrib
        return {attr: node.get(attr) for attr in self.attributes_identifiers if attr in node_attrib}

    def _get_descendants_axis_xpath(self, node: etree._Element, subtree: etree._Element | None = None) -> str:
        """Computes the xpath for `node` in terms of the descendants axis
        eg: [subtree]//[node's identification]
        If more than one node is found, the function returns an empty string

        subtree is a reference node for which we can compute the xpath separately
        """
        xpath_template = "//%s[@%s='%s']"
        if subtree is None:
            subtree = node.getroottree()
            is_subtree_element = False
        else:
            is_subtree_element = True

        tag = node.tag
        identifiers = self._get_identifiers(node)
        for name, value in identifiers.items():
            xpath_from_subtree = xpath_template % (tag, name, value)
            found = subtree.xpath("." + xpath_from_subtree)
            if found is not None and len(found) == 1:
                if is_subtree_element:
                    return self._get_xpath(subtree) + xpath_from_subtree
                return "." + xpath_from_subtree
        return ""

    def _get_children_axis_xpath(self, node: etree._Element, ancestors: list[etree._Element], subtree: etree._Element | None = None) -> str:
        """Computes the xpath of `node` in terms of direct children hierarchy
        eg: /form/div/notebook

        ancestors is in opposite order (bottom-up)
        subtree is a reference node for which we can compute the xpath separately
        """
        if subtree is not None:
            xpath = self._get_xpath(subtree)
        else:
            xpath = ""
        for ancestor in chain(reversed(ancestors), [node]):
            xpath += self._get_node_xpath(ancestor)
        return xpath

    def _get_node_xpath(self, node):
        """Computes the relative xpath of node in the context of its parent.
        Only the part concerning the location of the node inside the parent is returned
        eg: /field[@name='display_name'][1]
            /div[4]
        """
        identifiers = list(self._get_identifiers(node).items())
        main_identifier = identifiers and identifiers[0]

        iter_siblings = node.itersiblings(node.tag, preceding=True)
        if main_identifier:
            count = len([s for s in iter_siblings if s.get(main_identifier[0]) == main_identifier[1]])
        else:
            count = len(list(iter_siblings))
        count += 1  # As usual, xpath index starts at 1

        if main_identifier:
            local_xpath = f"/{node.tag}[@{main_identifier[0]}='{main_identifier[1]}']"
        else:
            local_xpath = f"/{node.tag}"

        if count > 1:
            local_xpath += f"[{count}]"

        return local_xpath

    def _get_xpath(self, node):
        subtree, ancestors = _get_subtree_and_ancestors(node, self.is_subtree)
        absolute = self._get_descendants_axis_xpath(node, subtree)
        if absolute:
            return absolute
        return self._get_children_axis_xpath(node, ancestors, subtree)

    def _redo_xpath_node(self, xpath_node, target_node):
        """Until now, we prepared "virtual" xpath nodes that have the correct position but only
        a target's DIFF ID as its expression.
        This method converts that virtual expression into its real XPATH representation,
        and applies some clean up to have deterministic output"""
        attribs = {}
        for attr in ("expr", "position"):
            attribs[attr] = xpath_node.attrib.pop(attr)
        for attr in xpath_node.attrib:
            xpath_node.attrib.pop(attr)

        for k, v in attribs.items():
            xpath_node.set(k, v)
        if target_node is not None and self.xpath_with_meta:
            for attr in target_node.attrib:
                if attr == DIFF_ATTRIBUTE:
                    continue
                xpath_node.set(f"meta-{attr}", target_node.get(attr))

    def _handle_node_full_replace(self, node_id, change):
        """When texts in an old node are incompatible with texts in a new node
        we replace the whole node by its new tag, attributes and contents.
        We don't want to loose references of its children though.
        So, we build a temporary node in which we push and move everything
        to replace the old node with that new one in a second operation
        """
        main_node = self.map_id_to_node_old[node_id]
        new_node = change["new_node"]
        attribs = dict(new_node.attrib)
        main_xpaths_list = []
        sub_xpath_list = []
        if len(new_node) == 0:
            replace_with = Element(main_node.tag, attribs)
            replace_with.text = new_node.text
            replace_xpath = Element("xpath", expr=node_id, position="replace", replace_all="1")
            replace_xpath.append(deepcopy(replace_with))
            main_xpaths_list.append(replace_xpath)
            return main_xpaths_list, sub_xpath_list

        # Append a temporary node inside the main one to store elements.
        # <oldnode>[*children]<tempnode /></oldnode>
        xpath_temp = Element("xpath", expr=node_id, position="inside")
        new_id = self.new_id
        self.new_id += 1
        new_node = Element(main_node.tag, attribs)
        new_node.set("o-diff-new-id", str(new_id))
        self.new_nodes_map[str(new_id)] = new_node

        xpath_temp.append(deepcopy(new_node))
        main_xpaths_list.append(xpath_temp)
        inside_temp_xpath = Element("xpath", expr=str(new_id), position="inside", new_target="1")
        main_xpaths_list.append(inside_temp_xpath)

        self.fill_xpath_node(change['new_leaves'], inside_temp_xpath, sub_xpath_list)

        # Replace the original node with the temporary one
        replace_with_temp = Element("xpath", expr=node_id, position="replace", replace_all="1")
        replace_with_temp.append(Element("xpath", expr=str(new_id), position="move", new_target="1"))
        main_xpaths_list.append(replace_with_temp)
        return main_xpaths_list, sub_xpath_list

    def _parse_old_leaves(self, leaves):
        """leaves represents the texts and nodes that were present in the old tree
        before or after a given pivot node.
        This function applies the changes on the old tree to determine
        what would be this old section of the tree once we remove or replace nodes.
        In Odoo's inheritance mechanism, moved nodes leave their tail behind, but removed
        nodes take their tail with them.
        This process allows, in a section of an old tree (before or after a pivot node),
        to select a removed node (replace_target) to build a replace xpath instead of a before/after
        one.
        """
        iter_leaves = iter(leaves)
        replace_target = None
        old_leaf = next(iter_leaves, None)
        old_leaves_with_removals = []
        while old_leaf:
            nid = isinstance(old_leaf, NodeLeaf) and old_leaf.element.get(DIFF_ATTRIBUTE)
            if nid and self.tracker.is_removed(nid, include_delayed=False):
                if replace_target is None:
                    replace_target = nid
                # The next leaf is necessarily a text-like one.
                # since the removal of a node implies the removal of its tail
                # we just ignore the removed node's tail.
                next(iter_leaves, None)
                old_leaves_with_removals.append(TextLeaf())
            else:
                append_leaf(old_leaves_with_removals, old_leaf)

            old_leaf = next(iter_leaves, None)
        return replace_target, old_leaves_with_removals

    def _leaves_text_compatibility(self, old_leaves, new_leaves, position):
        """Compares texts in old_leaves to new leaves according to position.
        The Odoo's inheritance mechanism doesn't really allow replacing texts
        This algorithm is used to determine beforehand if we can apply an xpath containing texts
        and whether to include a specific text or not in the xpath
        """
        left_old = left_new = right_old = right_new = None
        if old_leaves:
            left_old = old_leaves[0]
            if isinstance(old_leaves[-1], TextLeaf):
                right_old = old_leaves[-1]
        if new_leaves:
            left_new = new_leaves[0]
            right_new = new_leaves[-1]

        left = (left_old, left_new)
        right = (right_old, right_new)

        if position in ("before", "inside"):
            compare = [left]
        elif position == "after":
            compare = [right]
        elif position == "replace":
            compare = [left, right]

        for old, new in compare:
            old_text = old and old.element or None
            new_text = new and new.element or None
            compatible = old_text is None or old_text == new_text
            include_new = new_text is not None and old_text != new_text
            if not compatible:
                return False
            if not include_new and new_text:
                new.ignores.add(position)

        if position == "replace":
            # The replace instruction doesn't support the xpath node to have a text
            # and doesn't push tails if the element is a move xpath
            has_text = False
            has_moves = False
            for index, new_leaf in enumerate(new_leaves):
                if (
                    isinstance(new_leaf, TextLeaf)
                    and (index == 0 or has_moves)
                    and "replace" not in new_leaf.ignores
                    and new_leaf.element
                ):
                    has_text = True
                elif isinstance(new_leaf, NodeLeaf) and new_leaf.element.get(DIFF_ATTRIBUTE):
                    has_moves = True
                if has_text:
                    return False
        return True


class NodeTracker:
    def __init__(self, get_moving_candidate_key):
        self.get_moving_candidate_key = get_moving_candidate_key
        self.kept_ids = set()
        self.delayed_remove = set()
        self.move_ids = set()
        self.references = dict()
        self.candidates = dict()
        self.element_to_key = dict()

    def moving_candidate(self, node):
        key = self.get_moving_candidate_key(node)
        if key is not None:
            if key not in self.candidates:
                self.candidates[key] = node
                self.element_to_key[node] = key
                return key
            return key

    def moving_reference(self, node):
        key = self.get_moving_candidate_key(node)
        if key is not None and key not in self.references:
            self.references[key] = node
            self.element_to_key[node] = key
            return self.candidates.get(key)

    def get_from_key(self, key):
        ref = self.references.get(key)
        if ref is None or not self.element_to_key.get(ref):
            return (None, None)
        candid = self.candidates.get(key)
        if candid is not None:
            return ref, candid
        return (None, None)

    def is_removed(self, _id, include_delayed=True):
        rm = _id not in self.kept_ids
        if not include_delayed:
            return rm and _id not in self.delayed_remove
        return rm

    def delay_remove(self, _id):
        if _id:
            self.delayed_remove.add(_id)

    def keep(self, _id):
        if _id:
            self.kept_ids.add(_id)

    def move(self, _id):
        if _id:
            self.kept_ids.add(_id)
            self.move_ids.add(_id)

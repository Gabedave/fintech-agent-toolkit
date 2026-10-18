"""Finite, subject-bound interpretation of user-visible readiness propositions.

This module does not infer operations or policy. Unsupported candidate assertions
require independent disposition instead of being silently treated as compliant.
"""
import re


MARKER = re.compile('\\b(?:review-ready|merge-ready|ready|readiness)\\b')
TOKEN = re.compile("[a-z]+(?:'[a-z]+)?(?:-[a-z]+)*|#?\\d+")
PREDICATE_WORDS = set('''is are was were am be been being become becomes becoming
    will would could should can cannot may might does did do has have had
    not no never yet already now currently still fully actually apparently
    merely only just considered deemed declared marked called regarded as
    from to seem seems appear appears look looks sort kind of probably
    possibly almost tentatively isn't aren't wasn't weren't can't won't
    couldn't shouldn't wouldn't doesn't didn't don't hasn't haven't'''.split())
NEGATIVE = re.compile("\\b(?:not|no|never|cannot|can't|isn't|aren't|wasn't|weren't|won't|couldn't|shouldn't|wouldn't|doesn't|didn't|don't|hasn't|haven't)\\b")
HEDGES = set('seem seems appear appears look looks sort kind probably possibly almost tentatively may might could should would'.split())
CANDIDATES = set('change candidate pr patch code implementation work branch revision build fixture product production release submission deliverable artifact fix update modification tree'.split())
SUPPORTING = set('checklist list report assessment summary aggregate check checks test tests suite job gate environment service database storage infrastructure tool host probe attachment image capture document evidence control controls plan schedule meeting workspace script helper command blocker investigation'.split())
ACTORS = set('i we you they he she team reviewer investigator engineer developer operator'.split())
MODIFIERS = set('this that the our my your its these those current final synthetic proposed completed new existing updated fixed missing follow-up review real'.split())
REPORT_VERBS = '(?:claim|say|declare|assert|consider|call|describe|mark|label|confirm)'


def _role(head):
    if head in CANDIDATES or re.fullmatch('pr\\d+', head):
        return 'candidate'
    if head in SUPPORTING:
        return 'supporting'
    if head in ACTORS:
        return 'actor'
    if head in {'this', 'that'}:
        return 'candidate'
    return 'unknown'


def _subject(prefix, inherited):
    """Peel the local predicate, then classify its noun head, not nearby nouns."""
    tokens = list(TOKEN.finditer(prefix))
    index = len(tokens)
    while index and tokens[index - 1].group() in PREDICATE_WORDS:
        index -= 1
    predicate = ' '.join((token.group() for token in tokens[index:]))
    if not index or tokens[index - 1].group() == 'and':
        role = inherited or 'candidate' if index else 'candidate'
        return ('', role, predicate, prefix[:tokens[index].start()] if index < len(tokens) else prefix)
    head_index = index - 1
    head = tokens[head_index].group()
    if head.lstrip('#').isdigit() and head_index:
        head_index -= 1
        head = tokens[head_index].group()
    if head == 'request' and head_index and (tokens[head_index - 1].group() == 'pull'):
        head_index -= 1
        head = 'pr'
    if head == 'it':
        role = 'candidate' if inherited == 'candidate' else 'unknown'
    else:
        role = _role(head)
    start_index = head_index
    while start_index and tokens[start_index - 1].group() in MODIFIERS:
        start_index -= 1
    # A supporting noun with a candidate in a prepositional attachment remains
    # the subject: "the checklist for this PR is ready" concerns the checklist.
    prior = [token.group() for token in tokens[max(0, start_index - 4):start_index]]
    for position, token in enumerate(prior):
        if token in {'of', 'on', 'for', 'about', 'regarding'} and position:
            governing_role = _role(prior[position - 1])
            if governing_role != 'unknown':
                role = governing_role
    start = tokens[start_index].start()
    return (prefix[start:tokens[index - 1].end()].strip(), role, predicate, prefix[:start])


def _negated_report(prefix):
    return bool(re.search(
        """\\b(?:cannot|can't|don't|doesn't|didn't|not|never)\\s+(?:(?:yet|honestly|currently)\\s+)*"""
        +REPORT_VERBS + '(?:\\s+(?:that|as))?\\s*$'
        +'|\\b(?:refuse|decline)\\s+to\\s+' + REPORT_VERBS + '(?:\\s+that)?\\s*$'
        +'|\\bnot\\s+ready\\s+to\\s+' + REPORT_VERBS + '(?:\\s+that)?\\s*$'
        + r"|\bno\s+one\s+(?:can\s+)?" + REPORT_VERBS + r"(?:\s+that)?\s*$",
        prefix,
    ))


def _prevention(prefix, predicate):
    if 'from' not in predicate.split():
        return None
    verb = re.search(
        '\\b(?:prevent(?:s|ed|ing)?|stop(?:s|ped|ping)?|keep(?:s|ing)?|kept|block(?:s|ed|ing)?)\\s*$',
        prefix
    )
    if not verb:
        return None
    governing_predicate = ' '.join(prefix[:verb.start()].split()[-4:])
    return 'current' if NEGATIVE.search(governing_predicate) else 'negated'


def interpret_readiness(text):
    """Return scoped claims; kind is current/negated/future/unrelated/ambiguous.

    Only a supported present assertion about the candidate is a current claim.
    Missing subject/predicate grammar is ambiguous, never an automated pass.
    """
    text = text.lower().replace('’', "'")
    claims = []
    inherited = None
    sentences = re.split('([.;!?\\n]+)', text)
    clauses = []
    for index in range(0, len(sentences), 2):
        ending = sentences[index + 1] if index + 1 < len(sentences) else ''
        clauses.extend(((clause, '?' in ending) for clause in re.split('\\b(?:but|however|nevertheless)\\b', sentences[index])))
    for clause, question in clauses:
        for marker in MARKER.finditer(clause):
            prefix, suffix = (clause[:marker.start()], clause[marker.end():])
            subject, role, predicate, governor = _subject(prefix, inherited)
            if subject:
                inherited = role
            kind = 'ambiguous'
            positive_noun = re.match(
                '\\s+(?:(?:is|was|has|been|now|fully|not|never)\\s+)*(?:established|verified|confirmed|proven|achieved|complete|approved)\\b',
                suffix
            )
            if marker.group() == 'readiness' and (not positive_noun):
                # Mentioning the concept, a blocker, or a pending assessment does
                # not assert that the candidate is ready.
                continue
            local_predicate = predicate
            if positive_noun:
                local_predicate += ' ' + positive_noun.group()
            local_predicate = re.sub('\\bnot\\s+(?:only|merely|just)\\b', '', local_predicate)
            future_condition = bool(re.match('\\s+(?:(?:for|to|team|human|peer|a|the|review|merge|ship|publish|release|be|reviewed)\\s+)*(?:once|when|if)\\b', suffix))
            future_prefix = bool(re.search('\\b(?:once|when|if)\\b[^.;!?]*,\\s*$', governor))
            prevention = _prevention(governor, predicate)
            if NEGATIVE.search(local_predicate) or _negated_report(governor):
                kind = 'negated'
            elif 'will' in predicate.split():
                kind = 'future' if not {'now', 'currently'}.intersection(predicate.split()) else 'ambiguous'
            elif future_condition or future_prefix:
                # A conditional can encode a bypass or an already true premise.
                # Without explicit future tense, a human must resolve its scope.
                kind = 'ambiguous'
            elif role == 'supporting':
                kind = 'unrelated'
            elif role == 'actor':
                delivery = re.match(
                    '\\s+(?:for|to)\\s+(?:(?:team|human|peer|a|the)\\s+)*(?:review|merge|ship|publish|release)\\b',
                    suffix
                )
                kind = 'ambiguous' if delivery and subject in {
                    'i',
                    'we',
                    'you',
                    'they',
                    'team',
                    'the team'
                } else 'unrelated'
            elif role == 'candidate':
                if HEDGES.intersection(predicate.split()) or {'was', 'were', 'had'}.intersection(predicate.split()):
                    kind = 'ambiguous'
                else:
                    kind = prevention or 'current'
            if question and kind not in {'unrelated'}:
                kind = 'ambiguous'
            claims.append({'subject': subject or '(implicit candidate)', 'subject_role': role, 'predicate': predicate, 'kind': kind, 'claim': clause.strip()})
    return claims

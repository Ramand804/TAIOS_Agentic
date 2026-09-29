"""LangGraph orchestration for the isolated, mock-only V2 advisory boundary."""
from hashlib import sha256
from langgraph.graph import END, START, StateGraph
from agentic.adapter import resolve_advisory
from agentic.contracts import ValidationStatus
from agentic.graph_state import AgenticGraphState
from agentic.provenance import LLMProvenance

WORKFLOW_VERSION = 'v2-2b-mock-advisory-1'

def _raw_hash(reasoner, context):
    value = f'{type(reasoner).__name__}:{getattr(reasoner, "mode", "unknown")}:{context.planner_candidates}'
    return sha256(value.encode('utf-8')).hexdigest()

def build_mock_workflow(reasoner):
    """Compile an advisory-only workflow; it cannot authorize governance/execution."""
    def advisory(state: AgenticGraphState):
        # StateGraph accepts only typed state channels; evaluator fields are not channels.
        context = state['agentic_input']
        status, proposal, fallback = resolve_advisory(context, state['deterministic_proposal'], reasoner)
        provenance = LLMProvenance(
            llm_provider='mock', llm_model='deterministic-mock',
            prompt_version='v2-2b', response_schema_version='v1',
            raw_response_hash=_raw_hash(reasoner, context),
            validated_proposal=proposal if status == ValidationStatus.VALID else None,
            validation_status=status, fallback_reason=fallback)
        update = {'validation_status': status, 'resolved_proposal': proposal,
                  'fallback_reason': fallback, 'llm_provenance': provenance,
                  'workflow_version': WORKFLOW_VERSION, 'agentic_mode': 'AGENTIC_MOCK',
                  'visited_nodes': state.get('visited_nodes', ()) + ('agentic_advisory',)}
        if fallback is None:
            update['validated_advisory'] = proposal
        return update
    graph = StateGraph(AgenticGraphState)
    graph.add_node('agentic_advisory', advisory)
    graph.add_edge(START, 'agentic_advisory')
    graph.add_edge('agentic_advisory', END)
    return graph.compile()


def build_bounded_selection_workflow(reasoner, selector):
    """V2 graph segment after V1 planning/assurance; no governance or execution grant."""
    from agentic.bounded_selector import BoundedAgenticSelector
    def advisory(state):
        context = state['agentic_input']
        status, proposal, fallback = resolve_advisory(context, state['deterministic_proposal'], reasoner)
        return {'validation_status': status, 'validated_advisory': proposal if fallback is None else None,
                'resolved_proposal': proposal, 'fallback_reason': fallback,
                'visited_nodes': state.get('visited_nodes', ()) + ('agentic_advisory',),
                'agentic_mode': 'AGENTIC_MOCK'}
    def bounded_selection(state):
        decision, selection = selector.select(
            state['decision_context'], state['planning_result'], state.get('validated_advisory'),
            state['assurance_result'], state['authority_state'], state['validation_status'])
        return {'selected_decision': decision, 'selection_provenance': selection,
                'visited_nodes': state.get('visited_nodes', ()) + ('bounded_agentic_selection',)}
    graph = StateGraph(AgenticGraphState)
    graph.add_node('agentic_advisory', advisory)
    graph.add_node('bounded_agentic_selection', bounded_selection)
    graph.add_edge(START, 'agentic_advisory')
    graph.add_edge('agentic_advisory', 'bounded_agentic_selection')
    graph.add_edge('bounded_agentic_selection', END)
    return graph.compile()


def build_governed_mock_workflow(reasoner, selector, governance_agent, execution_agent):
    """Bounded V2 tail: advisory selection then unchanged V1 governance/execution."""
    graph = build_bounded_selection_workflow(reasoner, selector)
    # A compiled graph cannot be extended; construct the governed equivalent explicitly.
    def advisory(state):
        status, proposal, fallback = resolve_advisory(state['agentic_input'], state['deterministic_proposal'], reasoner)
        return {'validation_status': status, 'validated_advisory': proposal if fallback is None else None,
                'resolved_proposal': proposal, 'fallback_reason': fallback,
                'visited_nodes': state.get('visited_nodes', ()) + ('agentic_advisory',)}
    def selection(state):
        decision, provenance = selector.select(state['decision_context'], state['planning_result'], state.get('validated_advisory'), state['assurance_result'], state['authority_state'], state['validation_status'])
        return {'selected_decision': decision, 'selection_provenance': provenance,
                'visited_nodes': state.get('visited_nodes', ()) + ('bounded_agentic_selection',)}
    def governance(state):
        reviewed = governance_agent.review(state['decision_context'], state['planning_result'], state['selected_decision'])
        return {'governance_state': reviewed, 'visited_nodes': state.get('visited_nodes', ()) + ('governance',)}
    def execution(state):
        result = execution_agent.execute(state['decision_context'], state['planning_result'], state['selected_decision'], state['governance_state'], state['industrial_state'])
        return {'execution_state': result, 'visited_nodes': state.get('visited_nodes', ()) + ('execution',)}
    result = StateGraph(AgenticGraphState)
    result.add_node('agentic_advisory', advisory); result.add_node('bounded_agentic_selection', selection)
    result.add_node('governance', governance); result.add_node('execution', execution)
    result.add_edge(START, 'agentic_advisory'); result.add_edge('agentic_advisory', 'bounded_agentic_selection')
    result.add_edge('bounded_agentic_selection', 'governance'); result.add_edge('governance', 'execution'); result.add_edge('execution', END)
    return result.compile()

def build_transactional_runtime_workflow(runtime):
    """Graph entrypoint for transaction-owned V2 runtime processing.

    The runtime owns scientific mutation/rollback; LangGraph stores only event,
    result, terminal status, and visited-node trace.
    """
    class RuntimeState(dict): pass
    def begin(state): return {'visited_nodes':state.get('visited_nodes',())+('transaction_begin',)}
    def process(state):
        result=runtime.process_event(state['event'],state['industrial_state'])
        terminal=('PENDING_HUMAN_REVIEW' if result.execution_result.execution_status.value=='PENDING_APPROVAL' else 'COMPLETED')
        return {'result':result,'terminal_state':terminal,'visited_nodes':state.get('visited_nodes',())+('transactional_runtime',)}
    graph=StateGraph(AgenticGraphState); graph.add_node('transaction_begin',begin);graph.add_node('transactional_runtime',process)
    graph.add_edge(START,'transaction_begin');graph.add_edge('transaction_begin','transactional_runtime');graph.add_edge('transactional_runtime',END)
    return graph.compile()


def build_full_mock_lifecycle_workflow(pipeline, reasoner=None, *, working_memory=None,
                                       mode='AGENTIC_MOCK', memory_enabled=True):
    """Compile the source-derived, transaction-owned MockLLM lifecycle.

    Each node invokes exactly one extracted V1 lifecycle boundary.  The graph
    stores orchestration artifacts only; the pipeline remains the sole owner of
    scientific state and no LangGraph checkpointer is configured.
    """
    from core.experiment import fingerprint
    from core.pipeline_result import PipelineProcessingError
    from core.runtime_inputs import runtime_observation
    from environment.industrial_environment import IndustrialState
    from agentic.bounded_selector import BoundedAgenticSelector
    from agentic.contracts import AgenticInput
    from agentic.mock_llm import MockLLM
    from agentic.transaction import TAIOSTransactionContext
    from agentic.working_memory import WorkingMemory, retrieve

    reasoner = reasoner or MockLLM()
    selector = BoundedAgenticSelector()
    working_memory = working_memory or WorkingMemory()

    def visited(state, name, **values):
        values['visited_nodes'] = state.get('visited_nodes', ()) + (name,)
        return values

    def fail(state, exc):
        if isinstance(exc, PipelineProcessingError):
            raise exc
        stage = state.get('stage_holder', {'stage': 'event_validation'})['stage']
        tx = state.get('transaction')
        if tx is not None and not tx.committed and tx.failure_stage is None:
            tx.rollback(stage)
        pipeline._failure(stage, exc, state['event'], state['industrial_state'])

    def node(name, operation):
        def wrapped(state):
            try:
                update = operation(state)
                tx = state.get('transaction')
                if tx is not None:
                    tx.stage_complete(name)
                return visited(state, name, **update)
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                fail(state, exc)
        return wrapped

    def begin(state):
        event, industrial_state = state['event'], state['industrial_state']
        if type(industrial_state) is not IndustrialState:
            raise ValueError('Expected IndustrialState')
        input_ref = fingerprint(industrial_state.to_dict())
        key = getattr(event, 'event_id', None)
        prior = pipeline._processed_events.get(key)
        replay = prior is not None and fingerprint(runtime_observation(event)) == prior.event_reference and input_ref == fingerprint(prior.state_after.to_dict())
        return visited(state, 'transaction_begin', input_state_reference=input_ref,
                       event_key=key, replay=replay,
                       working_memory=working_memory,
                       stage_holder={'stage': 'event_validation'},
                       transaction=None if replay else TAIOSTransactionContext(pipeline).begin())

    def replay(state):
        result = pipeline.process_event(state['event'], state['industrial_state'])
        terminal = 'PENDING_HUMAN_REVIEW' if result.execution_result.execution_status.value == 'PENDING_APPROVAL' else 'COMPLETED'
        return visited(state, 'replay', result=result, terminal_state=terminal)

    def context(state):
        observation, before, transition = pipeline._event_observation(
            state['event'], state['industrial_state'], state['stage_holder'])
        return {'observation': observation, 'state_before': before, 'regime_transition': transition}

    def semantics(state):
        return {'semantics': pipeline._operational_semantics(state['observation'], state['stage_holder'])}

    def drift(state):
        reference, assessment, snapshot = pipeline._drift_assessment(
            state['observation'], state['semantics'], state['stage_holder'])
        return {'event_reference': reference, 'drift': assessment, 'reference_snapshot': snapshot}

    def authorization(state):
        return {'authorization': pipeline._authorization_assessment(state['observation'], state['stage_holder'])}

    def threat(state):
        return {'threat': pipeline._threat_assessment(
            state['observation'], state['semantics'], state['authorization'], state['stage_holder'])}

    def correlation(state):
        return {'correlation': pipeline._correlation_assessment(
            state['observation'], state['threat'], state['event_reference'], state['stage_holder'])}

    def trust(state):
        return {'trust': pipeline._trust_assessment(state['observation'], state['stage_holder'])}

    def risk(state):
        return {'risk': pipeline._risk_assessment(
            state['observation'], state['trust'], state['threat'], state['stage_holder'])}

    def decision_context(state):
        state['stage_holder']['stage'] = 'decision_context'
        authority, assurance, assured, context = pipeline._build_assured_decision_context(
            state['observation'], state['trust'], state['risk'], state['authorization'],
            state['semantics'], state['state_before'], state['event_reference'], state['drift'],
            state['threat'], state['correlation'], state['stage_holder'])
        return {'authority': authority, 'assurance_result': assurance,
                'assured_authority': assured, 'decision_context': context}

    def planning(state):
        plan = pipeline._planning(state['decision_context'], state['stage_holder'])
        return {'plan': plan, 'planning_result': plan}

    def decision(state):
        baseline = pipeline._baseline_decision(
            state['decision_context'], state['plan'], state['stage_holder'])
        return {'deterministic_proposal': baseline}

    def memory_retrieval(state):
        if not memory_enabled:
            return {'memory_retrieval': {'query': {}, 'retrieved_event_references': (),
                    'retrieved_count': 0, 'included_in_reasoning': False}, 'memory_context': ()}
        entries = retrieve(
            state['working_memory'],
            decision=(state['deterministic_proposal'].selected_action.value
                      if state['deterministic_proposal'].selected_action else None),
            drift=state['drift'].status.value)
        safe_entries = tuple({
            'event_reference': entry.event_reference, 'decision': entry.decision,
            'governance': entry.governance, 'execution': entry.execution,
            'drift': entry.drift} for entry in entries)
        return {'memory_retrieval': {
            'query': {'baseline_action': (state['deterministic_proposal'].selected_action.value
                                           if state['deterministic_proposal'].selected_action else None),
                      'drift': state['drift'].status.value},
            'retrieved_event_references': tuple(entry['event_reference'] for entry in safe_entries),
            'retrieved_count': len(safe_entries), 'included_in_reasoning': bool(safe_entries)},
            'memory_context': safe_entries}

    def llm_planning(state):
        context = state['decision_context']
        assured_actions = tuple(
            action for action, status in state['assured_authority'].action_authority.items()
            if status == 'PERMITTED')
        inp = AgenticInput(
            observation={'source_id': context.source_id, 'target_id': context.target_id,
                         'operation': context.observation['operation']},
            semantics=context.operational_semantic_assessment.to_dict(),
            authorization_status=context.authorization_status.value,
            trust_summary=context.trust_assessment.to_inference_dict(), threat_summary={},
            risk_summary=context.risk_assessment.to_inference_dict(), drift_summary={},
            adaptation_summary={}, assured_actions=assured_actions,
            planner_candidates=tuple(candidate.action.value for candidate in state['plan'].candidates),
            evidence_references=(context.reference, state['assurance_result'].reference),
            baseline_action=(state['deterministic_proposal'].selected_action.value
                             if state['deterministic_proposal'].selected_action else None),
            memory_context=state.get('memory_context', ()))
        status, proposal, fallback = resolve_advisory(inp, state['deterministic_proposal'], reasoner)
        metadata = getattr(getattr(reasoner, 'provider', reasoner), 'last_metadata', None)
        provenance = LLMProvenance(
            llm_provider=(metadata.provider if metadata else ('mock' if mode == 'AGENTIC_MOCK' else 'unavailable')),
            llm_model=(metadata.model if metadata else ('deterministic-mock' if mode == 'AGENTIC_MOCK' else 'unavailable')),
            prompt_version=(metadata.prompt_version if metadata else 'v2-2c'),
            response_schema_version=(metadata.schema_version if metadata else 'v1'),
            raw_response_hash=(metadata.response_hash if metadata else _raw_hash(reasoner, inp)),
            validated_proposal=proposal if status == ValidationStatus.VALID else None,
            validation_status=status, fallback_reason=fallback)
        return {'agentic_input': inp, 'validation_status': status,
                'validated_advisory': proposal if status == ValidationStatus.VALID else None,
                'resolved_proposal': proposal, 'fallback_reason': fallback,
                'llm_provenance': provenance, 'agentic_mode': mode}

    def bounded_selection(state):
        proposal, selection = selector.select(
            state['decision_context'], state['plan'], state.get('validated_advisory'),
            state['assurance_result'], state['authority'], state['validation_status'])
        return {'proposal': proposal, 'selected_decision': proposal,
                'selection_provenance': selection}

    def governance(state):
        return {'governance': pipeline._governance_review(
            state['decision_context'], state['plan'], state['proposal'], state['stage_holder'])}

    def execution(state):
        execution, after = pipeline._execute_decision(
            state['decision_context'], state['plan'], state['proposal'], state['governance'],
            state['state_before'], state['stage_holder'])
        return {'execution': execution, 'state_after': after}

    def outcome(state):
        return {'outcome': pipeline._observe_outcome(
            state['observation'], state['execution'], state['state_before'], state['state_after'],
            state['event_reference'], state['stage_holder'])}

    def experience(state):
        record = pipeline._commit_experience(
            event_reference=state['event_reference'], observation=state['observation'],
            semantics=state['semantics'], threat=state['threat'], correlation=state['correlation'],
            trust=state['trust'], risk=state['risk'], authorization=state['authorization'],
            authority=state['authority'], plan=state['plan'], proposal=state['proposal'],
            governance=state['governance'], execution=state['execution'], outcome=state['outcome'],
            state_before=state['state_before'], state_after=state['state_after'],
            stage_holder=state['stage_holder'])
        return {'experience': record}

    def feedback_interpretation(state):
        record = pipeline._interpret_feedback(
            state['experience'], state['outcome'], state['execution'], state['stage_holder'])
        return {'feedback': record}

    def feedback_commit(state):
        pipeline._commit_feedback(state['feedback'], state['stage_holder'])
        return {}

    def adaptation(state):
        proposal, decision = pipeline._behavioral_adaptation(
            state['observation'], state['semantics'], state['drift'], state['feedback'], state['stage_holder'])
        return {'adaptation_proposal': proposal, 'adaptation_decision': decision}

    def result(state):
        built = pipeline._build_pipeline_result(
            event=state['event'], event_reference=state['event_reference'], observation=state['observation'],
            trust=state['trust'], risk=state['risk'], authorization=state['authorization'],
            semantics=state['semantics'], drift=state['drift'], threat=state['threat'],
            correlation=state['correlation'], authority=state['authority'], context=state['decision_context'],
            plan=state['plan'], proposal=state['proposal'], governance=state['governance'],
            execution=state['execution'], outcome=state['outcome'], experience=state['experience'],
            feedback=state['feedback'], adaptation_proposal=state['adaptation_proposal'],
            adaptation_decision=state['adaptation_decision'], reference_snapshot=state['reference_snapshot'],
            assurance=state['assurance_result'], assured_authority=state['assured_authority'],
            input_state_reference=state['input_state_reference'], state_before=state['state_before'],
            state_after=state['state_after'], regime_transition=state['regime_transition'])
        pipeline._commit_processed_event(state['event_key'], built)
        terminal = 'PENDING_HUMAN_REVIEW' if built.execution_result.execution_status.value == 'PENDING_APPROVAL' else 'COMPLETED'
        return {'result': built, 'terminal_state': terminal}

    def commit(state):
        state['transaction'].commit()
        entry = state['working_memory'].append_result(state['result']) if memory_enabled else None
        return visited(state, 'transaction_commit', memory_commit=entry)

    def trace(state):
        from agentic.decision_trace import build_decision_trace
        return visited(
            state, 'trace',
            decision_trace=build_decision_trace(
                state['result'], agentic=state.get('validated_advisory'),
                selection=state.get('selection_provenance'),
                workflow={'version': 'v2-2c-full-lifecycle-1',
                          'mode': state.get('agentic_mode'),
                          'visited_nodes': state.get('visited_nodes', ()),
                          'memory_retrieval': state.get('memory_retrieval', {})}))

    graph = StateGraph(AgenticGraphState)
    graph.add_node('context', node('context', context))
    graph.add_node('semantics', node('semantics', semantics))
    graph.add_node('drift', node('drift', drift))
    graph.add_node('authorization', node('authorization', authorization))
    graph.add_node('threat', node('threat', threat))
    graph.add_node('correlation', node('correlation', correlation))
    graph.add_node('trust', node('trust', trust))
    graph.add_node('risk', node('risk', risk))
    graph.add_node('decision_context', node('decision_context', decision_context))
    graph.add_node('planning', node('planning', planning))
    graph.add_node('decision', node('decision', decision))
    graph.add_node('memory_retrieval', node('memory_retrieval', memory_retrieval))
    graph.add_node('llm_planning', node('llm_planning', llm_planning))
    graph.add_node('bounded_selection', node('bounded_selection', bounded_selection))
    graph.add_node('governance', node('governance', governance))
    graph.add_node('execution', node('execution', execution))
    graph.add_node('outcome', node('outcome', outcome))
    graph.add_node('experience', node('experience', experience))
    graph.add_node('feedback_interpretation', node('feedback_interpretation', feedback_interpretation))
    graph.add_node('feedback_commit', node('feedback_commit', feedback_commit))
    graph.add_node('adaptation', node('adaptation', adaptation))
    graph.add_node('result', node('result', result))
    graph.add_node('commit', commit)
    graph.add_node('trace', trace)
    graph.add_node('replay', replay)
    graph.add_node('begin', begin)
    graph.add_edge(START, 'begin')
    graph.add_conditional_edges('begin', lambda state: 'replay' if state['replay'] else 'context',
                                {'replay': 'replay', 'context': 'context'})
    chain = ('context', 'semantics', 'drift', 'authorization', 'threat', 'correlation', 'trust', 'risk',
             'decision_context', 'planning', 'decision', 'memory_retrieval', 'llm_planning', 'bounded_selection', 'governance',
             'execution', 'outcome', 'experience', 'feedback_interpretation', 'feedback_commit',
             'adaptation', 'result', 'commit', 'trace')
    for left, right in zip(chain, chain[1:]):
        graph.add_edge(left, right)
    graph.add_edge('replay', END)
    graph.add_edge('trace', END)
    return graph.compile()

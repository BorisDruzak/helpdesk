"""Admin-only draft walking; publication and requester execution stay strict.

Only missing continuations/default choices may be unfinished. This runtime
reuses canonical input normalization and traversal and never creates side effects.
"""
from copy import deepcopy

from tickets.request_scenario_runtime import ScenarioInputError, ScenarioRuntime
from tickets.request_scenario_validation import ScenarioValidationError, validate_scenario


def require_author_preview_definition(definition):
    blocks = {block.id: block for block in definition.blocks}
    rejected = []
    for issue in validate_scenario(definition):
        if issue.code in {'unreachable_block', 'unconnected_catalog_entry'}:
            continue
        if issue.code == 'processing_default_missing' and not getattr(definition.processing.defaults, issue.path.rsplit('.', 1)[-1]):
            continue
        if issue.code == 'missing_fallback':
            # Zero fallbacks is an unfinished route. Multiple fallbacks are an
            # ambiguous authored decision and must not acquire preview authority.
            block = blocks.get(issue.path.removeprefix('blocks.').removesuffix('.transitions'))
            if block and not any(edge.when is None for edge in block.transitions):
                continue
        rejected.append(issue)
    if rejected:
        raise ScenarioValidationError(rejected)


class _MissingContinuation(Exception):
    pass


class AuthorPreviewRuntime(ScenarioRuntime):
    _validate_definition = staticmethod(require_author_preview_definition)

    def _next(self, block, answers, result=None, action_key=None):
        try:
            return super()._next(block, answers, result, action_key)
        except ScenarioInputError as error:
            if set(error.errors) == {'transition'} and block.transition_mode != 'buttons':
                self._stopped_at = block.id
                raise _MissingContinuation() from error
            raise

    def _settle(self, state):
        try:
            return super()._settle(state)
        except _MissingContinuation:
            # Canonical automatic settling records a step immediately before
            # choosing its edge. An unfinished automatic step was not traversed.
            if state.history and state.history[-1] == state.current_block_id:
                state.history.pop()
            return state

    def advance(self, state, request):
        try:
            return super().advance(state, request)
        except _MissingContinuation:
            # super.advance already enforced revision/lifecycle/result checks;
            # retain canonical validated answers, without inventing a next step.
            result = deepcopy(state)
            block = self.blocks[state.current_block_id]
            if block.kind == 'form_page':
                result.answers = self._page_answers(block, state.answers, request.answers)
            elif request.current_result is not None:
                result.results[block.id] = request.current_result
            result.revision += 1
            return result

    def stop_for(self, state):
        block = self.blocks[state.current_block_id]
        if block.kind not in {'finish', 'submit_ticket'} and (not block.transitions or getattr(self, '_stopped_at', None) == block.id):
            return {'code': 'missing_continuation', 'block_id': block.id}
        return None

from test_script_generator.schemas import GeneratorState


def render_json_report(state: GeneratorState) -> dict:
    return state.model_dump(mode="json")

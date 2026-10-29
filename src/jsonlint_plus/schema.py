"""Optional JSON Schema validation using the jsonschema library."""
from jsonlint_plus.ast import inspect
from jsonlint_plus.parser import parse


def validate(source, schema):
    try:
        import jsonschema
        from referencing import Registry
    except ImportError:
        return [], 'Install jsonschema in the configured Python environment: python -m pip install jsonschema'
    try:
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        # No remote retrieval: internal references work, unknown external references fail visibly.
        validator = validator_cls(schema, registry=Registry())
        errors = list(validator.iter_errors(parse(source)))
        tree = inspect(source)['ast']
        diagnostics = []
        for error in errors:
            node = tree
            for part in error.absolute_path:
                children = node.get('children', [])
                if node['type'] == 'object':
                    property_node = next((child for child in children if child['key'] == part), None)
                    if property_node is None:
                        break
                    node = property_node['children'][0]
                elif node['type'] == 'array' and isinstance(part, int) and part < len(children):
                    node = children[part]
                else:
                    break
            diagnostics.append({'line': node['line'], 'column': node['column'], 'message': 'Schema: ' + error.message})
        return diagnostics, None
    except Exception as error:
        return [], f'JSON Schema validation failed: {error}'

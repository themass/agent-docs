// 零依赖的 JSON Schema 子集校验器(够用于本目录的 schema,不是通用实现)。
// 支持:$ref(#/$defs/..)、type(含数组)、enum、const、pattern、minLength/maxLength、minimum/maximum、
// required、properties、additionalProperties(bool|schema)、propertyNames.pattern、minProperties、
// items、minItems/maxItems、oneOf、anyOf。不认识的关键字会被忽略(如 description、title)。
// 返回错误字符串数组,空数组表示通过。

const typeOf = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : Number.isInteger(v) ? 'integer' : typeof v);
const typeOk = (v, t) => (t === 'number' ? typeof v === 'number' : t === 'integer' ? Number.isInteger(v) : typeOf(v) === t);

export function validate(schema, data, root = schema, path = '$') {
  const errs = [];
  const err = (m) => errs.push(`${path}: ${m}`);
  if (schema.$ref) {
    const target = schema.$ref.replace(/^#\//, '').split('/').reduce((o, k) => (o ? o[k] : undefined), root);
    if (!target) return [`${path}: unresolved $ref ${schema.$ref}`];
    return validate(target, data, root, path);
  }
  if (schema.oneOf) {
    const hits = schema.oneOf.filter((s) => validate(s, data, root, path).length === 0).length;
    if (hits !== 1) err(`must match exactly one of oneOf (matched ${hits})`);
  }
  if (schema.anyOf && !schema.anyOf.some((s) => validate(s, data, root, path).length === 0)) err('must match anyOf');
  if (schema.const !== undefined && data !== schema.const) err(`must equal ${JSON.stringify(schema.const)}`);
  if (schema.enum && !schema.enum.includes(data)) err(`must be one of ${JSON.stringify(schema.enum)}, got ${JSON.stringify(data)}`);
  if (schema.type) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some((t) => typeOk(data, t))) { err(`expected ${types.join('|')}, got ${typeOf(data)}`); return errs; }
  }
  if (typeof data === 'string') {
    const len = [...data].length;
    if (schema.minLength !== undefined && len < schema.minLength) err(`string shorter than ${schema.minLength}`);
    if (schema.maxLength !== undefined && len > schema.maxLength) err(`string longer than ${schema.maxLength}`);
    if (schema.pattern && !new RegExp(schema.pattern, 'u').test(data)) err(`does not match /${schema.pattern}/`);
  }
  if (typeof data === 'number') {
    if (schema.minimum !== undefined && data < schema.minimum) err(`below minimum ${schema.minimum}`);
    if (schema.maximum !== undefined && data > schema.maximum) err(`above maximum ${schema.maximum}`);
  }
  if (Array.isArray(data)) {
    if (schema.minItems !== undefined && data.length < schema.minItems) err(`fewer than ${schema.minItems} items`);
    if (schema.maxItems !== undefined && data.length > schema.maxItems) err(`more than ${schema.maxItems} items`);
    if (schema.items) data.forEach((x, i) => errs.push(...validate(schema.items, x, root, `${path}[${i}]`)));
  }
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const keys = Object.keys(data);
    for (const r of schema.required || []) if (!(r in data)) err(`missing required "${r}"`);
    if (schema.minProperties !== undefined && keys.length < schema.minProperties) err(`fewer than ${schema.minProperties} properties`);
    if (schema.propertyNames?.pattern) {
      const re = new RegExp(schema.propertyNames.pattern, 'u');
      for (const k of keys) if (!re.test(k)) err(`property name "${k}" does not match /${schema.propertyNames.pattern}/`);
    }
    const props = schema.properties || {};
    for (const k of keys) {
      if (k in props) errs.push(...validate(props[k], data[k], root, `${path}.${k}`));
      else if (schema.additionalProperties === false) err(`unexpected property "${k}"`);
      else if (schema.additionalProperties && typeof schema.additionalProperties === 'object')
        errs.push(...validate(schema.additionalProperties, data[k], root, `${path}.${k}`));
    }
  }
  return errs;
}

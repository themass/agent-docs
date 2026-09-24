import { clampDrawerWidth, DRAWER_WIDTH_MIN } from './drawer-layout'
import { parseLenient } from './json-lenient'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

{
  const ok = parseLenient('{"a":1}')
  assert(ok.repaired === false && (ok.value as { a: number }).a === 1, 'strict parse')
}
{
  const fixed = parseLenient('{a:1,}')
  assert(fixed.repaired === true && (fixed.value as { a: number }).a === 1, 'repair unquoted key + trailing comma')
}
{
  const brace = parseLenient('{{"a":1}')
  assert(brace.repaired === true && (brace.value as { a: number }).a === 1, 'repair extra brace')
}

assert(clampDrawerWidth(200, 1200) === DRAWER_WIDTH_MIN, 'drawer min width')
assert(clampDrawerWidth(2000, 1200) === 1200, 'drawer max width')

console.log('json-format self-check ok')

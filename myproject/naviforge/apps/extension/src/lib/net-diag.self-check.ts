import assert from 'node:assert/strict'

import {
  formatPublicIp,
  openStreetMapMarkerUrl,
  openStreetMapStaticUrl,
  type PublicIpInfo,
} from './net-diag'

const sample: PublicIpInfo = {
  ip: '1.2.3.4',
  country: 'CN',
  countryCode: 'CN',
  region: 'Shanghai',
  regionCode: 'SH',
  city: 'Shanghai',
  postalCode: '200000',
  continentCode: 'AS',
  latitude: 31.23,
  longitude: 121.47,
  timezone: 'Asia/Shanghai',
  offset: 28800,
  isp: 'Example ISP',
  organization: 'Example Org',
  asn: 'AS12345',
  asnOrganization: 'Example ASN Org',
  raw: {},
}
const text = formatPublicIp(sample)
assert(text.includes('1.2.3.4'), 'formats ip')
assert(text.includes('位置: CN / Shanghai / Shanghai'), 'formats location')
assert(text.includes('ISP: Example ISP'), 'formats isp')
assert(text.includes('ASN: AS12345'), 'formats asn')
assert(text.includes('坐标: 31.23, 121.47'), 'formats coords')
assert(text.includes('Asia/Shanghai'), 'formats timezone')
assert(
  openStreetMapMarkerUrl(31.23, 121.47).includes('mlat=31.23'),
  'osm marker link'
)
assert(
  openStreetMapStaticUrl(31.23, 121.47).includes('markers=31.23,121.47'),
  'osm static map'
)

console.log('net-diag self-check ok')

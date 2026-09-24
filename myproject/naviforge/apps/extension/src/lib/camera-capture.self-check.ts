import assert from 'node:assert/strict'

import { captureVideoFrame, cameraSettingsUrl, hasGetUserMedia, mediaErrorMessage, shouldMirrorPreview } from './camera-capture'

assert.ok(mediaErrorMessage({ name: 'NotAllowedError' }).includes('摄像头权限'))
assert.ok(mediaErrorMessage({ name: 'NotFoundError' }).includes('没有找到'))
assert.ok(mediaErrorMessage({ name: 'NotReadableError' }).includes('占用'))
assert.equal(mediaErrorMessage(new Error('boom')), 'boom')
assert.equal(shouldMirrorPreview('user'), true)
assert.equal(shouldMirrorPreview('environment'), false)
assert.equal(hasGetUserMedia(), false, 'node has no mediaDevices')
assert.equal(cameraSettingsUrl(), 'chrome://settings/content/camera')
assert.throws(
  () => captureVideoFrame({ videoWidth: 0, videoHeight: 0 } as HTMLVideoElement, false),
  /准备好/
)

console.log('camera-capture self-check ok')

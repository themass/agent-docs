import assert from 'node:assert/strict'

import { audioExtForMime, createVoiceRecorder, pickRecorderMime } from './audio-record'

assert.equal(audioExtForMime('audio/webm;codecs=opus'), '.webm')
assert.equal(audioExtForMime('audio/mp4'), '.m4a')
assert.equal(audioExtForMime('audio/mpeg'), '.mp3')
assert.equal(audioExtForMime('audio/ogg'), '.ogg')
assert.equal(audioExtForMime('audio/wav'), '.wav')
assert.equal(pickRecorderMime(), 'audio/webm', 'node has no MediaRecorder')
assert.equal(createVoiceRecorder(), null, 'node has no getUserMedia')

console.log('audio-record self-check ok')

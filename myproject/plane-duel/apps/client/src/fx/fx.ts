/**
 * 全客户端共享的 fx 单例。视图直接 import { fx, haptics }。
 * AudioContext 懒创建：首个 .play()（都在用户手势链路上）才初始化。
 */
import { createFx } from './audio'
import { createHaptics } from './haptics'

export const fx = createFx()
export const haptics = createHaptics()

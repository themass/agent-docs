/**
 * Interface wording only (button labels, empty states, explanations of what the app is doing).
 * Poems, history, annotations, lines spoken by anyone: NONE of that lives here, it all comes from
 * the bundle / poem pack. If a sentence states something about the poem or the past, it does not belong in this file.
 */
export const S = {
  appName: '诗词时空',
  demoBanner: '演示数据：文字来自内容底座的草稿，图片、人物和声音都是占位示意。都还没有发布，也不是史实。',
  offlineBanner: '现在没有网络，显示的是上次保存的内容。',
  mediaFailed: '图没加载出来，文字不受影响。',
  mediaOff: '已关闭图片与动画，文字照常。',
  steps: { read: '读', arrive: '到', meet: '见', return: '回', recite: '诵' },
  stepHints: {
    read: '先读一读，不懂哪一句，点一下它。',
    arrive: '四个地方，想看哪个点哪个，不用都看。',
    meet: '这位诗人是后人想象的样子，他说的话是演绎。',
    return: '选一句诗，看看刚才哪件事和它有关。',
    recite: '读一读，再用自己的话说说他为什么写这首诗。',
  },
  layers: { SCENE: '眼前', CITY: '这座城', WORLD: '这个天下', PERSON: '这个人' },
  depiction: '这是画师想象的示意形象，不是诗人的画像。',
  nudge: '还有几个地方你没看过，可能想知道。想继续也可以。',
  nav: { prev: '上一步', next: '下一步', skip: '跳过这一步', exit: '回到诗词页' },
  consent: {
    title: '先说一下我们记什么',
    body: '为了知道哪里没讲明白，我们只记：你看了哪一步、停留多久、点了什么。不记名字、学校、声音、照片，也不上传你写的话。你可以随时在“家长”里删除。',
    ok: '知道了',
    later: '先不记录',
  },
};

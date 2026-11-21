import { useRef, useState, type FormEvent } from 'react';
import { createTask, validationDetails } from '../api/client';
import { TASK_TYPES, type TaskType, type WorkSummary } from '../api/types';
import { useAnnounce } from '../components/announcer';
import { ErrorDetails } from '../components/error-details';
import { Button, Field } from '../components/ui';
import { useActor } from '../lib/actor';
import { describeError, errorCode } from '../lib/errors';
import { TASK_TYPE_INFO } from '../lib/labels';
import { navigate } from '../lib/router';

const MAX_INSTRUCTIONS = 4000;

type FieldName = 'work' | 'instructions' | 'title';
type FieldErrors = Partial<Record<FieldName, string>>;

/** 创建任务。指令是不可信材料:界面明确告知它不能越权,服务端会拒绝祈使式控制请求。 */
export function CreateTaskForm({ works }: { works: WorkSummary[] }) {
  const { actor, bodyActor, mode } = useActor();
  const announce = useAnnounce();
  const [workId, setWorkId] = useState(works[0]?.work_id ?? '');
  const [taskType, setTaskType] = useState<TaskType>('GAP_ANALYSIS');
  const [title, setTitle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<{ message: string; code?: string; details?: unknown } | null>(null);
  const [pending, setPending] = useState(false);
  const refs = {
    work: useRef<HTMLSelectElement>(null),
    title: useRef<HTMLInputElement>(null),
    instructions: useRef<HTMLTextAreaElement>(null),
  };

  const focusFirst = (found: FieldErrors) => {
    for (const name of ['work', 'title', 'instructions'] as const) {
      if (found[name]) {
        refs[name].current?.focus();
        return;
      }
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending) return;
    const found: FieldErrors = {};
    if (!workId) found.work = '请选择作品。';
    if (instructions.trim() === '') found.instructions = '请填写指令。';
    else if (instructions.length > MAX_INSTRUCTIONS) found.instructions = `指令不能超过 ${MAX_INSTRUCTIONS} 个字符。`;
    if (title.length > 200) found.title = '标题不能超过 200 个字符。';
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length > 0) {
      announce('表单有错误,请修正后再提交。', true);
      focusFirst(found);
      return;
    }
    const work = works.find(w => w.work_id === workId);
    const finalTitle = title.trim() || `${work?.title ?? workId} · ${TASK_TYPE_INFO[taskType].label}`;
    setPending(true);
    try {
      const task = await createTask({
        work_id: workId,
        title: finalTitle,
        task_type: taskType,
        instructions: instructions.trim(),
        ...(bodyActor ? { actor: bodyActor } : {}),
      });
      announce('任务已创建。');
      navigate(`/tasks/${encodeURIComponent(task.task_id)}`);
    } catch (error) {
      const info = describeError(error);
      const next: FieldErrors = {};
      if (info.code === 'WORK_NOT_FOUND') next.work = info.message;
      else if (info.status === 422) {
        for (const detail of validationDetails(error)) {
          const field = detail.loc.find(part => part === 'instructions' || part === 'title' || part === 'work_id');
          if (field === 'title') next.title = detail.message;
          else if (field === 'work_id') next.work = detail.message;
          else next.instructions = detail.message;
        }
        if (Object.keys(next).length === 0) next.instructions = info.message;
      }
      setErrors(next);
      setFormError({ message: info.message, code: errorCode(error), details: info.details });
      announce(`创建失败:${info.message}`, true);
      if (Object.keys(next).length > 0) focusFirst(next);
    } finally {
      setPending(false);
    }
  };

  return (
    <section aria-labelledby="create-title" className="panel">
      <h2 id="create-title">创建任务</h2>
      <p className="notice notice--info">
        <strong>指令是不可信材料,不能越权。</strong>
        它只作为参考交给 agent,不会被当作命令执行。要求“发布”“核验来源”“删除内容”“执行 SQL”之类的指令会被拒绝(422)。
      </p>
      <form onSubmit={submit} noValidate aria-describedby={formError ? 'create-error' : undefined}>
        {formError ? (
          <div id="create-error" className="notice notice--error" role="alert">
            <p>
              <span aria-hidden="true">✕ </span>
              {formError.message}
              {formError.code ? (
                <>
                  {' '}
                  <code>{formError.code}</code>
                </>
              ) : null}
            </p>
            <ErrorDetails details={formError.details} />
          </div>
        ) : null}

        <Field id="ct-work" label="作品" error={errors.work}>
          {aria => (
            <select {...aria} ref={refs.work} value={workId} onChange={event => setWorkId(event.target.value)}>
              {works.length === 0 ? <option value="">(没有可选作品)</option> : null}
              {works.map(w => (
                <option key={w.work_id} value={w.work_id}>
                  {w.title}({w.work_id})
                </option>
              ))}
            </select>
          )}
        </Field>

        <fieldset className="fieldset">
          <legend>任务类型</legend>
          {TASK_TYPES.map(type => (
            <label key={type} className="radio radio--block">
              <input type="radio" name="task-type" value={type} checked={taskType === type} onChange={() => setTaskType(type)} />
              <span>
                <strong>{TASK_TYPE_INFO[type].label}</strong> <code>{type}</code>
                <span className="radio__desc">{TASK_TYPE_INFO[type].description}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <Field id="ct-title" label="标题(可选)" hint="留空则自动生成:作品名 · 任务类型。" error={errors.title}>
          {aria => <input {...aria} ref={refs.title} value={title} onChange={event => setTitle(event.target.value)} />}
        </Field>

        <Field
          id="ct-instructions"
          label="指令"
          hint={`说明你希望 agent 关注什么。最多 ${MAX_INSTRUCTIONS} 字,当前 ${instructions.length}。`}
          error={errors.instructions}
        >
          {aria => (
            <textarea
              {...aria}
              ref={refs.instructions}
              rows={5}
              value={instructions}
              onChange={event => setInstructions(event.target.value)}
            />
          )}
        </Field>

        <p className="field__hint">
          {mode === 'off' ? (
            <>将以 <code>{actor.actor_id}</code>({actor.role})的占位身份提交。</>
          ) : (
            <>将以登录身份 <code>{actor.actor_id}</code>({actor.role})提交,身份由令牌决定。</>
          )}
        </p>
        <Button variant="primary" type="submit" blocked={pending} aria-busy={pending}>
          {pending ? '正在创建…' : '创建任务'}
        </Button>
      </form>
    </section>
  );
}

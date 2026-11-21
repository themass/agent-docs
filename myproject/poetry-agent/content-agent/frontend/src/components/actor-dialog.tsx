import { useState, type FormEvent } from 'react';
import { ROLES, type Role } from '../api/types';
import { useActor } from '../lib/actor';
import { ROLE_LABEL } from '../lib/labels';
import { PERMISSION_MATRIX } from '../lib/permissions';
import { looksLikeAgent } from '../lib/validation';
import { useAnnounce } from './announcer';
import { Dialog } from './dialog';
import { Button, Field } from './ui';

export function ActorDialog({ onClose }: { onClose: () => void }) {
  const { actor, setActor } = useActor();
  const announce = useAnnounce();
  const [id, setId] = useState(actor.actor_id);
  const [role, setRole] = useState<Role>(actor.role);
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    if (id.trim() === '') {
      setError('actor id 不能为空。');
      return;
    }
    setActor({ actor_id: id, role });
    announce(`当前身份已切换为 ${id.trim()},${ROLE_LABEL[role]}`);
    onClose();
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save();
  };

  const warn = looksLikeAgent(id) && id.trim() !== '';

  return (
    <Dialog
      title="当前 actor(占位身份)"
      onClose={onClose}
      footer={
        <>
          <Button variant="quiet" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" onClick={save}>
            保存身份
          </Button>
        </>
      }
    >
      <p className="notice notice--warn">
        当前是<strong>离线演示模式,使用未接入登录的占位身份</strong>:id 与角色由本页自行填写并存在浏览器 localStorage,随请求体提交。
        服务端只校验角色白名单,无法证明你是谁。启用登录(auth_mode=required)后本选择器会被登录替换。
      </p>
      <form id="actor-form" onSubmit={submit} noValidate>
        <Field
          id="actor-id"
          label="actor id"
          error={error}
          hint={
            warn
              ? '提示:该 id 含 agent/bot/ai 等字样,评审与核验时会被后端拒绝。'
              : '用于评审与审计的署名,2–100 个字符。'
          }
        >
          {aria => (
            <input
              {...aria}
              data-autofocus
              value={id}
              onChange={event => {
                setId(event.target.value);
                setError(null);
              }}
              autoComplete="off"
            />
          )}
        </Field>
        <fieldset className="fieldset">
          <legend>角色</legend>
          {ROLES.map(r => (
            <label key={r} className="radio">
              <input type="radio" name="actor-role" value={r} checked={role === r} onChange={() => setRole(r)} />
              <span>
                {ROLE_LABEL[r]} <code>{r}</code>
              </span>
            </label>
          ))}
        </fieldset>
      </form>
      <table className="matrix">
        <caption>各角色能做什么(服务端为准)</caption>
        <thead>
          <tr>
            <th scope="col">动作</th>
            {ROLES.map(r => (
              <th scope="col" key={r}>
                {ROLE_LABEL[r]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {PERMISSION_MATRIX.map(row => (
            <tr key={row.action}>
              <th scope="row">{row.action}</th>
              {ROLES.map(r => (
                <td key={r}>{row.roles.includes(r) ? '可以' : '不可'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Dialog>
  );
}

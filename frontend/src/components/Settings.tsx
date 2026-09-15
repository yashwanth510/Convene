import { useEffect, useRef } from "react";
import { X, SlidersHorizontal } from "lucide-react";
import type { Settings as Preferences, Model } from "../lib/types";
export default function Settings({
  open,
  close,
  value,
  change,
  models,
}: {
  open: boolean;
  close: () => void;
  value: Preferences;
  change: (value: Preferences) => void;
  models: Model[];
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) ref.current?.showModal();
    else ref.current?.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="settings-dialog"
      onCancel={close}
      onClick={(e) => {
        if (e.target === ref.current) close();
      }}
    >
      <div className="dialog-inner">
        <header>
          <div>
            <span className="eyebrow">Make it yours</span>
            <h2>
              <SlidersHorizontal size={21} /> Council settings
            </h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close settings"
            onClick={close}
          >
            <X size={20} />
          </button>
        </header>
        <p className="quiet">
          Choose the depth of discussion. More models and rounds take more time
          and API requests.
        </p>
        <label>
          Default approach
          <select
            value={value.mode}
            onChange={(e) =>
              change({ ...value, mode: e.target.value as Preferences["mode"] })
            }
          >
            <option value="auto">Auto · match the question</option>
            <option value="fast">Quick · one model</option>
            <option value="council">Council · compare perspectives</option>
          </select>
        </label>
        <div className="settings-grid">
          <label>
            Panel size
            <select
              value={value.panel_size}
              onChange={(e) =>
                change({ ...value, panel_size: Number(e.target.value) })
              }
            >
              {[2, 3, 4].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
          <label>
            Review rounds
            <select
              value={value.debate_rounds}
              onChange={(e) =>
                change({ ...value, debate_rounds: Number(e.target.value) })
              }
            >
              {[1, 2, 3].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="section-label">Available perspectives</div>
        <div className="model-list">
          {models.map((model) => (
            <label className="model-row" key={model.id}>
              <input
                type="checkbox"
                checked={value.enabled_models.includes(model.id)}
                disabled={model.status !== "active" || !model.configured}
                onChange={(e) =>
                  change({
                    ...value,
                    enabled_models: e.target.checked
                      ? [...value.enabled_models, model.id]
                      : value.enabled_models.filter((id) => id !== model.id),
                  })
                }
              />
              <span>
                <strong>{model.name}</strong>
                <small>
                  {model.provider} ·{" "}
                  {model.status !== "active"
                    ? "inactive"
                    : !model.configured
                      ? "not configured"
                      : model.last_status}
                </small>
              </span>
            </label>
          ))}
        </div>
        <p className="quiet small">
          Only enabled models participate, including fallbacks. The free router
          can choose a model already represented; duplicate answers are excluded
          from voting.
        </p>
        <button className="primary" onClick={close}>
          Done
        </button>
      </div>
    </dialog>
  );
}

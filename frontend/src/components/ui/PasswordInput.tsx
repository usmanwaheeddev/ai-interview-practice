import {useState, type InputHTMLAttributes} from "react";
import {Input} from "./Field";

export function PasswordInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [visible, setVisible] = useState(false);
  const label = visible ? "Hide password" : "Show password";

  return <span className="relative block">
    <Input {...props} type={visible ? "text" : "password"} className={`pr-11 ${props.className ?? ""}`} />
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={() => setVisible(value => !value)}
      className="absolute inset-y-0 right-0 grid w-11 place-items-center text-ink-500 transition hover:text-brand-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500"
    >
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {visible
          ? <><path d="M3 3l18 18"/><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 4.2A10.8 10.8 0 0 1 12 4c5.5 0 9 6 9 8a12.7 12.7 0 0 1-2.1 3.3M6.6 6.6C4.3 8.1 3 10.7 3 12c0 2 3.5 8 9 8 1.2 0 2.3-.3 3.3-.7"/></>
          : <><path d="M3 12s3.5-8 9-8 9 8 9 8-3.5 8-9 8-9-8-9-8Z"/><circle cx="12" cy="12" r="2.5"/></>}
      </svg>
    </button>
  </span>;
}

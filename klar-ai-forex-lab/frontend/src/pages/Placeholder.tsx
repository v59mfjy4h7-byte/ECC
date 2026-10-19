import { Card } from "../components/Common";

export default function Placeholder({ title, milestone, text }: { title: string; milestone?: string; text: string }) {
  return (
    <Card title={title}>
      {milestone && <p className="mb-2 text-sm font-medium text-slate-500 dark:text-slate-400">Byggs i {milestone} – inte implementerat ännu.</p>}
      <p className="text-sm">{text}</p>
    </Card>
  );
}

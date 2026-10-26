import { ShortlistScreen } from "@/components/shortlist-screen";
export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string }> }) { const { run } = await searchParams; return <ShortlistScreen key={run || "latest"} runId={run}/>; }

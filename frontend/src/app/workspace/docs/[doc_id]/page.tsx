import { redirect } from "next/navigation";

export default async function DocumentPageRedirect({
  params,
}: {
  params: Promise<{ doc_id: string }>;
}) {
  const { doc_id } = await params;
  redirect(`/workspace/composer/${doc_id}`);
}

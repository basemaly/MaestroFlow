import { redirect } from "next/navigation";

export default function DocumentsPageRedirect() {
  redirect("/workspace/composer");
}

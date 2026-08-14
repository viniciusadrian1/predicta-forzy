import { redirect } from "next/navigation";

// A home operacional agora é /overview; o catálogo de ativos vive em /assets.
export default function DashboardRedirect() {
  redirect("/overview");
}

import { redirect } from "next/navigation";

// Assistente unificado: a antiga tela de chat com a base técnica agora vive
// dentro do Volt. Mantemos a rota só para não quebrar links antigos.
export default function ChatRedirect() {
  redirect("/volt");
}

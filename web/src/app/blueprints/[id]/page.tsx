import { notFound } from "next/navigation";
import { getProjectById } from "@/lib/turso";
import BlueprintReader from "@/components/BlueprintReader";

export const revalidate = 60;

type Props = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: Props) {
  const { id } = await params;
  const project = await getProjectById(id);
  if (!project) {
    return {
      title: "Blueprint Not Found | JHunt",
    };
  }
  return {
    title: `${project.title} | JHunt Blueprint`,
    description: `Production portfolio architecture spec for ${project.role} in ${project.domain || "Tech"}.`,
  };
}

export default async function BlueprintDetailPage({ params }: Props) {
  const { id } = await params;
  const project = await getProjectById(id);

  if (!project) {
    return notFound();
  }

  return <BlueprintReader project={project} />;
}

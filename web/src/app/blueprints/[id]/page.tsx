import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getProjectById } from "@/lib/turso";
import BlueprintReader from "@/components/BlueprintReader";

export const revalidate = 60;
export const dynamicParams = true;

export async function generateStaticParams() {
  return [];
}

type Props = {
  params: Promise<{ id: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const project = await getProjectById(id);
  if (!project) {
    return {
      title: "Blueprint Not Found",
      description: "The requested architecture blueprint could not be found.",
    };
  }

  const techTags = project.tech_stack
    ? project.tech_stack
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean)
    : [];
  const description = `Production portfolio architecture spec for ${project.role} in ${project.domain || "Tech"}. Features: ${techTags.slice(0, 4).join(", ") || "Production Stack"}. Difficulty: ${project.difficulty}.`;

  return {
    title: project.title,
    description,
    openGraph: {
      title: `${project.title} | JHunt Blueprint`,
      description,
      type: "article",
      publishedTime: project.created_at,
      tags: techTags,
    },
    twitter: {
      card: "summary_large_image",
      title: `${project.title} | JHunt Blueprint`,
      description,
    },
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

import { type ReactNode } from "react";
import { Nav, type Breadcrumb } from "@/components/nav";

interface LayoutProps {
  children: ReactNode;
  breadcrumbs?: Breadcrumb[];
}

export default function Layout({ children, breadcrumbs }: LayoutProps) {
  return (
    <div className="min-h-screen bg-paper flex flex-col">
      <Nav breadcrumbs={breadcrumbs} />
      <main className="w-full px-8 py-7 pb-20">
        {children}
      </main>
    </div>
  );
}

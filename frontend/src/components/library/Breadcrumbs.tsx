import React from "react";
import { ChevronRight, HardDrive } from "lucide-react";
import type { BreadcrumbItem } from "@/types/library";

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  onNavigate: (folderId: string, name?: string) => void;
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ items, onNavigate }) => {
  return (
    <nav className="flex items-center gap-1.5 text-xs sm:text-sm text-text-muted overflow-x-auto py-1">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        const isRoot = index === 0;

        return (
          <React.Fragment key={item.id}>
            {index > 0 && <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 text-border" />}
            <button
              type="button"
              onClick={() => onNavigate(item.id, item.name)}
              disabled={isLast}
              className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors flex-shrink-0 ${
                isLast
                  ? "font-medium text-text bg-surface/50 pointer-events-none"
                  : "hover:text-text hover:bg-surface text-text-muted"
              }`}
            >
              {isRoot && <HardDrive className="w-3.5 h-3.5 text-accent-1" />}
              <span>{item.name}</span>
            </button>
          </React.Fragment>
        );
      })}
    </nav>
  );
};

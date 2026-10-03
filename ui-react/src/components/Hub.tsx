// After sign-in: new project or an existing one (D-184).
import { FolderOpen, FolderPlus } from "lucide-react";
import { Headline, Tagline, Tile } from "./landing";
import { Button } from "./ui";

export function Hub({ user, projectCount, onNew, onOpen }: { user: string | null; projectCount: number; onNew: () => void; onOpen: () => void }) {
  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <Tile className="flex flex-1 flex-col items-center justify-center px-8 py-14 text-center md:basis-1/2 md:justify-start md:pt-[26vh]">
        <Headline>Start something new.</Headline>
        <Tagline className="mt-3 max-w-md">
          {user ? `Hello, ${user}. ` : ""}Build a standalone project, or work on a copy of an existing repository.
        </Tagline>
        <Button variant="primary" className="mt-6 h-11 px-6 text-[15px]" icon={<FolderPlus className="h-4 w-4" />} onClick={onNew}>
          New project
        </Button>
      </Tile>
      <Tile dark className="flex flex-1 flex-col items-center justify-center px-8 py-14 text-center md:basis-1/2 md:justify-start md:pt-[26vh]">
        <Headline>Pick up where you left off.</Headline>
        <Tagline className="mt-3 max-w-md">
          {projectCount === 0
            ? "Projects you have worked on will appear here, with their memory and history."
            : `${projectCount} project${projectCount === 1 ? "" : "s"}. Forge resumes from what it remembers.`}
        </Tagline>
        <Button
          variant="primary"
          className="mt-6 h-11 px-6 text-[15px]"
          icon={<FolderOpen className="h-4 w-4" />}
          disabled={projectCount === 0}
          onClick={onOpen}
        >
          Open a project
        </Button>
      </Tile>
    </div>
  );
}

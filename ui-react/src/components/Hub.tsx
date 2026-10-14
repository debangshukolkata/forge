// After sign-in: new project or an existing one (D-184).
import { FolderOpen, FolderPlus } from "lucide-react";
import { Headline, Tagline, Tile } from "./landing";
import { Button } from "./ui";

// On wide screens the two tiles share their rows (headline, tagline, button) through a subgrid, so the buttons sit on one line
// even when the text of one side wraps and the other's does not.
const TILE =
  "flex flex-1 flex-col items-center justify-center px-8 py-14 text-center md:row-span-4 md:grid md:grid-rows-subgrid md:justify-items-center md:gap-0 md:pt-[26vh]";

export function Hub({ user, projectCount, onNew, onOpen }: { user: string | null; projectCount: number; onNew: () => void; onOpen: () => void }) {
  return (
    <div className="flex min-h-full flex-col md:grid md:grid-cols-2 md:grid-rows-[auto_auto_auto_1fr]">
      <Tile className={TILE}>
        <Headline>Start something new.</Headline>
        <Tagline className="mt-3 max-w-md">{user ? `Hello, ${user}. ` : ""}Build a project, or work on a repository copy.</Tagline>
        <Button variant="primary" className="mt-6 h-11 px-6 text-[15px]" icon={<FolderPlus className="h-4 w-4" />} onClick={onNew}>
          New project
        </Button>
      </Tile>
      <Tile dark className={TILE}>
        <Headline>Continue a project.</Headline>
        <Tagline className="mt-3 max-w-md">
          {projectCount === 0 ? "Your projects will appear here." : `${projectCount} project${projectCount === 1 ? "" : "s"}, with their memory.`}
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

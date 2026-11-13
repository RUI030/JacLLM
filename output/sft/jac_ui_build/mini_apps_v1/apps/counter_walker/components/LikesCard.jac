import from "@hugeicons/react" { HugeiconsIcon }
import from "@hugeicons/core-free-icons" { StarIcon }
import from .ui.button { Button }
import from .ui.card { Card, CardContent }
sv import from ..services.likes { LikeCount, open_likes, add_like }

def:pub LikesCard() -> JsxElement {
    has total: int = 0;
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn open_likes();
            if len(result.reports) > 0 {
                total = result.reports[0].total as int;
            }
        } except Exception as e {
            error = "Could not load the likes.";
        }
        loading = False;
    }

    async def handle_like() -> None {
        try {
            result = root spawn add_like();
            if len(result.reports) > 0 {
                total = result.reports[0].total as int;
            }
            error = "";
        } except Exception as e {
            error = "Could not save the like.";
        }
    }

    label = "1 like" if total == 1 else str(total) + " likes";

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
            <CardContent className="flex flex-col items-center gap-5 pt-2 pb-2 text-center">
                <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <HugeiconsIcon icon={StarIcon} strokeWidth={2} className="size-5" />
                </div>
                <h1 className="text-2xl font-semibold tracking-tight">{"Likes"}</h1>
                <span className="text-4xl font-semibold tracking-tight tabular-nums">{"Loading..." if loading else label}</span>
                {error and <p className="text-sm text-destructive">{error}</p>}
                <Button className="w-full shadow-sm" onClick={lambda -> None { handle_like(); }}>{"Like"}</Button>
            </CardContent>
        </Card>
    </div>;
}

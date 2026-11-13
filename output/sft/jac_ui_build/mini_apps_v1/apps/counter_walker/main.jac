import from services.likes { LikeCount, open_likes, add_like }

import ".styles.global.css";
import from .components.LikesCard { LikesCard }

def:pub app() -> JsxElement {
    return <LikesCard />;
}

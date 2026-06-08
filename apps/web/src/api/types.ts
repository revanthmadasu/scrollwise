// TypeScript mirrors of the API's Pydantic schemas (apps/api/app/schemas).
// When apps/api publishes an OpenAPI spec to packages/contract, these can be
// replaced by generated types.

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  preferred_level: number;
}

export interface Topic {
  topic_id: string;
  title: string;
  description: string;
}

export interface Interests {
  topic_ids: string[];
}

export type PromptStatus = "pending" | "generating" | "ready" | "failed";

export interface Prompt {
  id: string;
  prompt_text: string;
  status: PromptStatus;
  topic_id: string | null;
  error: string | null;
  created_at: string;
}

export type ContentType = "text" | "image_post" | "carousel" | "video" | "test";
export type Reaction = "like" | "dislike";

export interface Post {
  post_id: string;
  topic_id: string;
  subtopic_id: string;
  level: number;
  content_type: ContentType;
  title: string;
  body: string;
  image_urls: string[];
  post_image_urls: string[];
  video_url: string | null;
  estimated_duration_sec: number;
  test_type: string | null;
  question: string | null;
  options: string[] | null;
  blocking: boolean;
  my_reaction: Reaction | null;
  like_count: number;
}

export type FeedReason = "remediation" | "prompted" | "suggested";

export interface FeedItem {
  post: Post;
  reason: FeedReason;
}

export interface FeedResponse {
  items: FeedItem[];
}

export interface ReactionResult {
  post_id: string;
  my_reaction: Reaction | null;
  like_count: number;
  dislike_count: number;
}

export interface AnswerResult {
  post_id: string;
  is_correct: boolean;
  correct_index: number;
  explanation: string | null;
  remediation_queued: boolean;
}

export interface TopicProgress {
  topic_id: string;
  cursor_module: number;
  cursor_subtopic: number;
  cursor_seq: number;
  posts_seen: number;
  total_posts: number;
}

export interface Progress {
  topics: TopicProgress[];
  tests_taken: number;
  tests_passed: number;
}

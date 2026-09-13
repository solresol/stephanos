CREATE TABLE IF NOT EXISTS grammar_review_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    target_key TEXT NOT NULL,
    passage_sha256 TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('correct','bless','reject','restore','unbless')),
    reviewer TEXT NOT NULL,
    review_note TEXT NOT NULL DEFAULT '',
    sentence_note TEXT NOT NULL DEFAULT '',
    literal_translation TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS grammar_review_action_tokens (
    event_key TEXT NOT NULL REFERENCES grammar_review_actions(event_key),
    token_order INTEGER NOT NULL,
    form TEXT NOT NULL, lemma TEXT NOT NULL, upos TEXT NOT NULL, xpos TEXT NOT NULL,
    head_token_id TEXT NOT NULL, deprel TEXT NOT NULL, confidence TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '', grammatical_role TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(event_key,token_order)
);
CREATE TABLE IF NOT EXISTS grammar_review_action_features (
    event_key TEXT NOT NULL, token_order INTEGER NOT NULL,
    feature_name TEXT NOT NULL, feature_value TEXT NOT NULL,
    PRIMARY KEY(event_key,token_order,feature_name),
    FOREIGN KEY(event_key,token_order) REFERENCES grammar_review_action_tokens(event_key,token_order)
);
CREATE TABLE IF NOT EXISTS grammar_review_action_issues (
    event_key TEXT NOT NULL REFERENCES grammar_review_actions(event_key),
    token_id TEXT NOT NULL, issue_text TEXT NOT NULL,
    PRIMARY KEY(event_key,token_id)
);

-- M7 chronological evidence ordering independent of transaction-stable now() and UUIDs.
ALTER TABLE ago_executive_snapshots
 ADD COLUMN capture_order bigint GENERATED ALWAYS AS IDENTITY;
CREATE UNIQUE INDEX ago_exec_capture_order_unique
 ON ago_executive_snapshots(capture_order);

ALTER TABLE ago_meta_recommendations
 ADD COLUMN recommendation_order bigint GENERATED ALWAYS AS IDENTITY;
CREATE UNIQUE INDEX ago_meta_recommendation_order_unique
 ON ago_meta_recommendations(recommendation_order);

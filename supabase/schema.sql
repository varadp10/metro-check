
-- (Dashboard -> SQL Editor -> New query -> paste -> Run)

create table if not exists scans (
    id bigint generated always as identity primary key,
    product_name text,
    scan_time text,
    compliance_score int,
    passed_fields int,
    total_fields int,
    details_json text,
    image_path text
);


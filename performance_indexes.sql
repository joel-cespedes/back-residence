-- Add performance indexes for residents query
-- These indexes will significantly improve the performance of the residents listing query

-- Index on resident.residence_id for filtering by residence
CREATE INDEX IF NOT EXISTS idx_resident_residence_id ON resident(residence_id);

-- Index on resident.deleted_at for soft delete filtering
CREATE INDEX IF NOT EXISTS idx_resident_deleted_at ON resident(deleted_at) WHERE deleted_at IS NULL;

-- Index on resident.bed_id for bed joining
CREATE INDEX IF NOT EXISTS idx_resident_bed_id ON resident(bed_id);

-- Index on resident.status for filtering by status
CREATE INDEX IF NOT EXISTS idx_resident_status ON resident(status);

-- Composite index for residence + status filtering (common combination)
CREATE INDEX IF NOT EXISTS idx_resident_residence_status ON resident(residence_id, status);

-- Index on bed.room_id for room joining
CREATE INDEX IF NOT EXISTS idx_bed_room_id ON bed(room_id);

-- Index on room.floor_id for floor joining
CREATE INDEX IF NOT EXISTS idx_room_floor_id ON room(floor_id);

-- Index on floor.residence_id for residence filtering
CREATE INDEX IF NOT EXISTS idx_floor_residence_id ON floor(residence_id);

-- Index on resident.created_at for sorting and date filtering
CREATE INDEX IF NOT EXISTS idx_resident_created_at ON resident(created_at);

-- Text search index on resident.full_name for search functionality
CREATE INDEX IF NOT EXISTS idx_resident_full_name_search ON resident USING gin(to_tsvector('spanish', full_name));

-- Text search index on resident.comments for search functionality
CREATE INDEX IF NOT EXISTS idx_resident_comments_search ON resident USING gin(to_tsvector('spanish', comments));
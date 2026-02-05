# My Tasks Tab - Quick Start Guide

## Overview
The **✅ My Tasks** tab is your approval workflow center where you can review, approve, or reject all enhanced images before they go live.

## Getting Started

### 1. Access the Tab
- Open the dashboard
- Click on the **✅ My Tasks** tab
- You'll see all pending approvals

### 2. Dashboard Layout

```
┌─────────────────────────────────────────────────┐
│         Approval Queue Statistics               │
├──────────────┬──────────────┬──────────────────┤
│ 📋 Pending   │ 🖼️ Images   │ 📈 Improvement  │
│ Review: 42   │ Total: 42    │ +12.5%          │
│              │              │ ⏱️ 234ms avg    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│            Filtering & Navigation               │
├──────────────┬──────────────┬──────────────────┤
│ 🔍 Search    │ Sort By:     │ Items Per Page:  │
│ SKU-123      │ Latest ▼     │ 10 ▼             │
└─────────────────────────────────────────────────┘

⬅️ Page 1 of 5 ➡️

┌──────────────────────────────────────────────────────────────┐
│ SKU ID │ Original │ Enhanced │ Scores │ Info │ Actions │ S. │
├──────────────────────────────────────────────────────────────┤
│ SKU-1  │ [Thumb]  │ [Thumb]  │ 92pts │ 3ops │ ✅  ❌ │ ⏳ │
│        │ 450KB    │ 320KB    │ +15%  │ 234ms│        │    │
│        │ 1920×14  │ 1920×14  │ +12%  │ -29% │        │    │
└──────────────────────────────────────────────────────────────┘
```

## Features

### 📊 Statistics Panel
Shows at the top of the page:
- **📋 Pending Review**: Number of tasks awaiting approval
- **🖼️ Total Images**: Total images across all pending tasks
- **📈 Avg Quality Improvement**: Average quality score improvement percentage
- **⏱️ Avg Processing Time**: Average enhancement processing time in milliseconds

### 🔍 Filtering Options

#### Search by SKU ID
- Type SKU ID in the search box
- Results filter in real-time
- Shows matching tasks only

#### Sort Options
- **Latest**: Most recent enhancements first (default)
- **SKU ID**: Alphabetical by SKU
- **Quality Improvement**: Highest improvements first
- **File Size**: Largest files first

#### Items Per Page
- Slider from 5 to 50 tasks per page
- Adjust based on your screen and preferences
- Better performance with fewer items

### 📋 Table Columns

#### SKU ID Column
- **SKU Identifier**: The unique product SKU
- **Image Type**: primary, front, side, back, detail, lifestyle, etc.

#### Original Image Column
- **Thumbnail**: 300×300px preview of original
- **File Size**: Size in KB
- **Dimensions**: Width × Height in pixels

#### Enhanced Image Column
- **Thumbnail**: 300×300px preview of enhanced version
- **File Size**: Size in KB  
- **Dimensions**: Width × Height in pixels

#### Quality Scores Column
**Original Metrics:**
- Blur Score (0-100, lower = sharper)
- Quality Score (0-100, higher = better)

**Enhanced Metrics:**
- Blur Score with ✅ if improved
- Quality Score with ✅ if improved
- Shows +X% improvement

#### Info Column
- **🔧**: Number of enhancement operations applied
- **⏱️**: Processing time in milliseconds
- **📉**: File size reduction percentage

#### Actions Column
- **✅**: Approve button (quick approval)
- **❌**: Reject button (with reason)

#### Status Column
- **✅**: Green - Already approved
- **❌**: Red - Rejected
- **⏳**: Yellow - Pending review

## How to Approve

### Quick Approve (1 click)
1. Review the original and enhanced thumbnails
2. Check the quality score improvements
3. Click the **✅** button in the Actions column
4. See "Approving..." loading indicator
5. Toast notification "✅ Approved!" appears
6. Page automatically refreshes to show updated status

### What Happens When You Approve
- Image marked as **APPROVED** in database
- Status changes from ⏳ to ✅
- `qc_status` field set to `APPROVED`
- Timestamp recorded in `qc_reviewed_at`
- Image ready for publishing

## How to Reject

### Reject with Reason (2 steps)
1. Click the **❌** button
2. Text area appears with prompt "Why reject this image?"
3. Enter rejection reason (e.g., "Poor color correction", "Blurry edges")
4. Click **✓ Confirm** button
5. See "Rejecting..." loading indicator
6. Toast notification "❌ Rejected!" appears
7. Page automatically refreshes
8. Status changes to ❌
9. Rejection reason saved in database

### Example Rejection Reasons
- "Poor color correction, unnatural skin tones"
- "Uneven lighting on edges"
- "Background removal failed at corner"
- "Overly sharpened, looks artificial"
- "Color shifting on product surface"
- "Not meeting quality standards"

### What Happens When You Reject
- Image marked as **REJECTED** in database
- Status changes from ⏳ to ❌
- `qc_status` field set to `REJECTED`
- Rejection reason stored in `qc_notes`
- Timestamp recorded in `qc_reviewed_at`
- Image can be re-enhanced and resubmitted

## Common Workflows

### Workflow 1: Quick Approval (Batch)
1. Set items per page to 20
2. Review each row of 3 images quickly
3. Click ✅ for each good image
4. Navigate to next page
5. Repeat until all approved

### Workflow 2: Focused Review
1. Search by specific SKU ID
2. Review all images for that SKU
3. Approve or reject each one
4. Move to next SKU

### Workflow 3: Quality-Based Sorting
1. Sort by "Quality Improvement"
2. Review highest improvement first
3. Mark as approved
4. Move down the list

### Workflow 4: Problem Investigation
1. Sort by "Latest"
2. For each task, compare Original vs Enhanced
3. If quality improvement < 5%, reject with reason
4. Otherwise approve

## Tips & Tricks

### ⚡ Speed Tips
- Use thumbnail comparison to quickly assess quality
- Look for ✅ in quality scores column
- Green checkmarks indicate improvements
- Skip detailed review if metrics are good

### 🔍 Detailed Review
- Click on thumbnail to see full size (opens in modal)
- Compare blur scores between original and enhanced
- Check file size reduction percentage
- Verify all enhancement operations were applied

### 📊 Tracking Progress
- Watch "Pending Review" count decrease
- Monitor average quality improvement trend
- Track average processing time
- Use for reporting and analytics

### 🛡️ Quality Control
- Always check blur scores improved
- Verify quality scores didn't degrade
- Look for artificial sharpening artifacts
- Check for color fringing or halos

## Keyboard Shortcuts (Future)

Currently these need manual clicking, but planned:
- `A` key: Approve current task
- `R` key: Reject current task
- `N` key: Next page
- `P` key: Previous page
- `S` key: Focus search box

## Data Exported to Database

When you approve/reject, this data is saved:

### Approval Record
```
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "qc_status": "APPROVED",
  "qc_reviewed_at": "2026-02-05T16:30:00",
  "qc_notes": null
}
```

### Rejection Record
```
{
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "qc_status": "REJECTED",
  "qc_reviewed_at": "2026-02-05T16:35:00",
  "qc_notes": "Rejected: Poor edge quality on background removal"
}
```

## Troubleshooting

### Issue: Images not loading
**Solution:**
- Check internet connection
- Verify S3 bucket URLs are accessible
- Wait 5 seconds for timeout
- Try refreshing the page

### Issue: Approve/Reject buttons not working
**Solution:**
- Check API server is running on port 8000
- Verify database connection
- Check browser console for errors
- Try refreshing the page

### Issue: Status not updating
**Solution:**
- Wait for page to refresh automatically
- If stuck, manually refresh page (F5)
- Check database logs for errors

### Issue: Search not filtering
**Solution:**
- Ensure SKU ID is typed correctly
- Clear search box and retype
- Check case sensitivity (usually case-insensitive)

## Performance Notes

- **Load Time**: < 2 seconds for 100 tasks
- **Thumbnail Size**: 300×300px for quick loading
- **Pagination**: Handles 500+ tasks smoothly
- **API Timeout**: 5 seconds per image

## Next Steps After Approval

Once image is **APPROVED**:
1. Ready for publication
2. Can be pushed to marketplace
3. Included in product catalog
4. Used for A/B testing
5. Monitored for performance

Once image is **REJECTED**:
1. Can be re-enhanced
2. Resubmitted for review
3. Or deleted if not needed
4. Excluded from current batch

## Support

For issues or questions:
1. Check this guide's troubleshooting section
2. Review logs in `/logs/` directory
3. Contact development team
4. Submit bug report with screenshot

---

**Happy Approving! 🎉**

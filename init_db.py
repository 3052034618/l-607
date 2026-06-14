"""
城市建筑垃圾运输与处置智能调度系统 - 初始化脚本
创建默认管理员账号、企业、执法队等基础数据
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, Base, engine
from app.models import (
    User, Enterprise, EnforcementTeam, UserRole, EnterpriseType,
    ConstructionSite, DisposalSite, Vehicle,
)
from app.utils.security import hash_password


def init_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                real_name="系统管理员",
                phone="13800000000",
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            print("创建默认管理员账号: admin / admin123")

        construction_ent = db.query(Enterprise).filter(
            Enterprise.name == "示例建筑工程有限公司"
        ).first()
        if not construction_ent:
            construction_ent = Enterprise(
                name="示例建筑工程有限公司",
                type=EnterpriseType.CONSTRUCTION,
                unified_social_credit_code="91110000MA01CONS01",
                legal_person="张建设",
                contact_person="李经理",
                contact_phone="13811111111",
                address="北京市朝阳区建国路100号",
            )
            db.add(construction_ent)
            db.flush()
            print("创建示例施工企业")

        transport_ent = db.query(Enterprise).filter(
            Enterprise.name == "示例渣土运输有限公司"
        ).first()
        if not transport_ent:
            transport_ent = Enterprise(
                name="示例渣土运输有限公司",
                type=EnterpriseType.TRANSPORT,
                unified_social_credit_code="91110000MA01TRANS01",
                legal_person="王运输",
                contact_person="赵调度",
                contact_phone="13822222222",
                address="北京市丰台区丰台路200号",
            )
            db.add(transport_ent)
            db.flush()
            print("创建示例运输企业")

        construction_user = db.query(User).filter(User.username == "construction").first()
        if not construction_user:
            construction_user = User(
                username="construction",
                password_hash=hash_password("test123"),
                real_name="施工方账号",
                phone="13833333333",
                role=UserRole.CONSTRUCTION_UNIT,
                enterprise_id=construction_ent.id,
            )
            db.add(construction_user)
            print("创建施工方账号: construction / test123")

        transport_user = db.query(User).filter(User.username == "transport").first()
        if not transport_user:
            transport_user = User(
                username="transport",
                password_hash=hash_password("test123"),
                real_name="运输方账号",
                phone="13844444444",
                role=UserRole.TRANSPORT_COMPANY,
                enterprise_id=transport_ent.id,
            )
            db.add(transport_user)
            print("创建运输方账号: transport / test123")

        city_management_user = db.query(User).filter(User.username == "city").first()
        if not city_management_user:
            city_management_user = User(
                username="city",
                password_hash=hash_password("test123"),
                real_name="城管账号",
                phone="13855555555",
                role=UserRole.CITY_MANAGEMENT,
            )
            db.add(city_management_user)
            print("创建城管账号: city / test123")

        team = db.query(EnforcementTeam).filter(EnforcementTeam.team_code == "ENF001").first()
        if not team:
            team = EnforcementTeam(
                name="朝阳区第一执法队",
                team_code="ENF001",
                region="朝阳区",
                team_leader="刘执法",
                contact_phone="13866666666",
                workload_weight=1.0,
            )
            db.add(team)
            db.flush()
            print("创建示例执法队")

        enforcement_user = db.query(User).filter(User.username == "enforcement").first()
        if not enforcement_user:
            enforcement_user = User(
                username="enforcement",
                password_hash=hash_password("test123"),
                real_name="执法队员",
                phone="13877777777",
                role=UserRole.ENFORCEMENT_TEAM,
                enforcement_team_id=team.id,
            )
            db.add(enforcement_user)
            print("创建执法队员账号: enforcement / test123")

        site = db.query(ConstructionSite).filter(ConstructionSite.site_code == "CS001").first()
        if not site:
            site = ConstructionSite(
                site_code="CS001",
                name="朝阳CBD核心区A地块项目",
                enterprise_id=construction_ent.id,
                address="北京市朝阳区建国路与东三环交汇处",
                district="朝阳区",
                latitude=39.9163,
                longitude=116.4610,
                project_manager="陈工",
                contact_phone="13888888888",
                total_expected_volume=50000.0,
                remaining_volume=50000.0,
                daily_max_transports=100,
            )
            db.add(site)
            print("创建示例工地")

        disposal1 = db.query(DisposalSite).filter(DisposalSite.site_code == "DS001").first()
        if not disposal1:
            disposal1 = DisposalSite(
                site_code="DS001",
                name="朝阳区东坝消纳场",
                address="北京市朝阳区东坝乡",
                district="朝阳区",
                latitude=39.9658,
                longitude=116.5210,
                total_capacity=500000.0,
                remaining_capacity=350000.0,
                daily_acceptance_limit=5000.0,
                daily_accepted=0,
                contact_person="孙场长",
                contact_phone="13899999999",
            )
            db.add(disposal1)
            print("创建示例消纳场1")

        disposal2 = db.query(DisposalSite).filter(DisposalSite.site_code == "DS002").first()
        if not disposal2:
            disposal2 = DisposalSite(
                site_code="DS002",
                name="通州宋庄消纳场",
                address="北京市通州区宋庄镇",
                district="通州区",
                latitude=39.9810,
                longitude=116.7170,
                total_capacity=800000.0,
                remaining_capacity=620000.0,
                daily_acceptance_limit=8000.0,
                daily_accepted=0,
                contact_person="周场长",
                contact_phone="13700000000",
            )
            db.add(disposal2)
            print("创建示例消纳场2")

        vehicle1 = db.query(Vehicle).filter(Vehicle.plate_number == "京A·12345").first()
        if not vehicle1:
            vehicle1 = Vehicle(
                plate_number="京A·12345",
                vehicle_type="重型自卸货车",
                load_capacity=25.0,
                container_volume=16.0,
                enterprise_id=transport_ent.id,
                driver_name="李师傅",
                driver_phone="13711111111",
                gps_device_id="GPS001",
                has_sealing_device=True,
            )
            db.add(vehicle1)

        vehicle2 = db.query(Vehicle).filter(Vehicle.plate_number == "京A·67890").first()
        if not vehicle2:
            vehicle2 = Vehicle(
                plate_number="京A·67890",
                vehicle_type="重型自卸货车",
                load_capacity=25.0,
                container_volume=16.0,
                enterprise_id=transport_ent.id,
                driver_name="王师傅",
                driver_phone="13722222222",
                gps_device_id="GPS002",
                has_sealing_device=True,
            )
            db.add(vehicle2)
            print("创建2台示例车辆")

        db.commit()
        print("\n数据库初始化完成！")
        print("默认测试账号：")
        print("  管理员:   admin / admin123")
        print("  施工单位: construction / test123")
        print("  运输企业: transport / test123")
        print("  城管:     city / test123")
        print("  执法队:   enforcement / test123")

    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
